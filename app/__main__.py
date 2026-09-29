"""Entry point: ``python -m app``."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ErrorEvent

from app.commands import set_user_commands, setup_default_commands
from app.config import get_settings
from app.db import create_engine, create_session_factory, init_db
from app.db.fsm_storage import DbStorage
from app.db.repo import Access
from app.handlers import admin, common, registration, staff
from app.i18n import t
from app.middlewares import DbSessionMiddleware, UserContextMiddleware
from app.services import vision
from app.services.backup import backup_loop
from app.services.documents import cleanup_uploads

log = logging.getLogger("app")


async def on_error(event: ErrorEvent) -> None:
    exc = event.exception
    update = event.update
    callback = update.callback_query
    if isinstance(exc, TelegramBadRequest) and "message is not modified" in str(exc):
        if callback:
            with contextlib.suppress(Exception):
                await callback.answer()
        return
    log.exception("Unhandled error in update %s", update.update_id, exc_info=exc)
    tg_user = (update.message or callback or update.edited_message)
    tg_user = tg_user.from_user if tg_user else None
    lang = tg_user.language_code if tg_user and tg_user.language_code in {"uz", "ru", "en"} else None
    text = t(lang, "error.generic")
    with contextlib.suppress(Exception):
        if callback:
            await callback.answer(text, show_alert=True)
        elif update.message:
            await update.message.answer(text)


async def cleanup_loop(session_factory, settings) -> None:
    """Hourly: remove website uploads that no document references any more."""
    while True:
        try:
            removed = await cleanup_uploads(session_factory, settings.uploads_dir)
            if removed:
                log.info("Removed %d unreferenced uploaded files", removed)
        except Exception:
            log.exception("Uploads cleanup failed")
        await asyncio.sleep(3600)


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    engine = create_engine(settings.database_url)
    await init_db(engine)
    session_factory = create_session_factory(engine)

    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    dp = Dispatcher(storage=DbStorage(session_factory), settings=settings, sessions=session_factory)
    dp.update.outer_middleware(DbSessionMiddleware(session_factory))
    dp.update.outer_middleware(UserContextMiddleware(settings))
    # Order matters: generic handlers (cancel, /start) first, catch-all last.
    dp.include_routers(common.router, admin.router, staff.router, registration.router, common.fallback_router)
    dp.errors.register(on_error)

    background: list[asyncio.Task] = []
    try:
        me = await bot.me()
        await setup_default_commands(bot)
        for admin_id in settings.admin_ids:
            await set_user_commands(bot, admin_id, None, Access(is_admin=True))
        log.info("Starting @%s (admins=%s)", me.username, settings.admin_ids)
        # Load the OCR / face models now rather than on the first student's photo.
        background.append(asyncio.create_task(asyncio.to_thread(vision.warm_up), name="vision-warm-up"))
        background.append(asyncio.create_task(cleanup_loop(session_factory, settings), name="uploads-cleanup"))
        if settings.backup_enabled:
            background.append(asyncio.create_task(backup_loop(bot, settings, session_factory), name="backups"))
            log.info("Daily backup at %s (%s) into %s", settings.backup_time, settings.timezone, settings.backup_dir)
            if not settings.backup_password:
                log.warning("BACKUP_PASSWORD is not set: backups are NOT encrypted")

        if not settings.web_enabled:
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
            return

        import signal

        import uvicorn

        from app.web import create_app

        class Server(uvicorn.Server):
            @contextlib.contextmanager
            def capture_signals(self):  # signals are handled below, for bot and web together
                yield

        web = create_app(settings=settings, sessions=session_factory, bot=bot)
        server = Server(
            uvicorn.Config(
                web,
                host=settings.web_host,
                port=settings.web_port,
                proxy_headers=True,
                forwarded_allow_ips="*",
                log_level=settings.log_level.lower(),
                access_log=False,
            )
        )
        log.info("Web panel on %s (listening on %s:%s)", settings.web_base_url, settings.web_host, settings.web_port)

        async def stop_polling() -> None:
            with contextlib.suppress(RuntimeError):  # not running (yet/any more)
                await dp.stop_polling()

        def shutdown() -> None:
            log.info("Shutting down…")
            server.should_exit = True
            asyncio.ensure_future(stop_polling())

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, shutdown)

        async def run_web() -> None:
            try:
                await server.serve()
            finally:
                await stop_polling()  # e.g. the port is taken: don't leave the bot running alone

        web_task = asyncio.create_task(run_web(), name="web")
        try:
            await dp.start_polling(
                bot, allowed_updates=dp.resolve_used_update_types(), handle_signals=False
            )
        finally:
            server.should_exit = True
            await web_task
    finally:
        for task in background:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
