from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db import repo
from app.i18n import Translator
from app.services.prefs import load_prefs

log = logging.getLogger(__name__)

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class DbSessionMiddleware(BaseMiddleware):
    """Opens one session per update; commits on success, rolls back on error."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        async with self.session_factory() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
            except Exception:
                await session.rollback()
                raise
            await session.commit()
            return result


class UserContextMiddleware(BaseMiddleware):
    """Registers the Telegram user and injects ``user``, ``access`` and ``_``."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        chat = data.get("event_chat")
        if tg_user is None or tg_user.is_bot or (chat is not None and chat.type != "private"):
            return None  # the bot works in private chats only
        session: AsyncSession = data["session"]
        user = await repo.upsert_user(session, tg_user)
        # Release SQLite's write lock before the handler starts talking to Telegram.
        await session.commit()
        data["user"] = user
        data["access"] = await repo.get_access(session, tg_user.id, self.settings.admin_ids)
        data["_"] = Translator(user.language)
        data["prefs"] = await load_prefs(session, self.settings)
        return await handler(event, data)
