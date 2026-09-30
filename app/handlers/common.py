"""Start, language, help, cancel, staff sign-in (/login, /logout), fallback."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import defaultdict, deque
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app import keyboards as kb
from app.callbacks import LangCb
from app.commands import set_user_commands
from app.config import Settings
from app.db import repo
from app.db.models import Language, StaffRole, User, utcnow
from app.db.repo import Access
from app.handlers.ui import delete_quietly, drop_screen, screen
from app.i18n import LANGUAGE_PROMPT, Translator, menu_buttons, variants
from app.services.passwords import DUMMY_HASH, verify_password
from app.states import LoginStates
from app.views import render_roles

log = logging.getLogger(__name__)
router = Router(name="common")

LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW = 15 * 60
_login_failures: defaultdict[int, deque[float]] = defaultdict(deque)


async def show_main_menu(
    message: Message,
    session: AsyncSession,
    user: User,
    access: Access,
    _: Translator,
    *,
    text: str | None = None,
) -> None:
    """Send the home message with the persistent reply keyboard."""
    student = await repo.get_student_by_tg(session, user.id)
    if text is None:
        if access.is_staff:
            account = await repo.get_account_by_telegram(session, user.id)
            groups = [r.group.name for r in (account.roles if account else []) if r.role == StaffRole.LEADER and r.group]
            name = account.label if account else (user.first_name or "")
            text = _("welcome.staff", name=escape(name), roles=render_roles(_, access, groups))
        elif student:
            text = _("welcome.back", name=escape(student.first_name or student.full_name))
        else:
            await message.answer(_("welcome.new"), reply_markup=kb.consent_kb(_))
            return
    await message.answer(text, reply_markup=kb.main_menu(_, access, is_registered=student is not None))


# ------------------------------------------------------------------ /start


@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext, session: AsyncSession, user: User, access: Access, _: Translator, bot: Bot
) -> None:
    await drop_screen(bot, message.chat.id, state)
    await state.clear()
    if user.language is None:
        await message.answer(LANGUAGE_PROMPT, reply_markup=kb.language_kb())
        return
    await set_user_commands(bot, user.id, user.language, access)
    await show_main_menu(message, session, user, access, _)


# ------------------------------------------------------------------ language


@router.message(Command("language"))
@router.message(F.text.in_(variants("btn.language")))
async def cmd_language(message: Message) -> None:
    await message.answer(LANGUAGE_PROMPT, reply_markup=kb.language_kb())


@router.callback_query(LangCb.filter())
async def on_language(
    cb: CallbackQuery, callback_data: LangCb, state: FSMContext, session: AsyncSession, user: User, access: Access, bot: Bot
) -> None:
    user.language = Language(callback_data.code)
    _ = Translator(user.language)
    await session.commit()  # before touching FSM storage (separate DB connection)
    await cb.answer(_("lang.changed"))
    with contextlib.suppress(Exception):
        await cb.message.delete()
    await set_user_commands(bot, user.id, user.language, access)
    if await state.get_state() is None:
        await show_main_menu(cb.message, session, user, access, _)


# ------------------------------------------------------------------ help & cancel


@router.message(Command("help"))
@router.message(F.text.in_(variants("btn.help")))
async def cmd_help(message: Message, access: Access, _: Translator) -> None:
    text = _("help.staff") if access.is_staff else _("help.student")
    if access.is_admin:
        text += _("help.admin")
    await message.answer(text)


async def _cancel(message: Message, state: FSMContext, session: AsyncSession, user: User, access: Access, _: Translator, bot: Bot) -> None:
    await drop_screen(bot, message.chat.id, state)
    await state.clear()
    await show_main_menu(message, session, user, access, _, text=_("cancelled"))


@router.message(Command("cancel"))
@router.message(F.text.in_(variants("btn.cancel")))
async def cmd_cancel(message: Message, state: FSMContext, session: AsyncSession, user: User, access: Access, _: Translator, bot: Bot) -> None:
    await _cancel(message, state, session, user, access, _, bot)


@router.callback_query(F.data == "cancel")
async def on_cancel(cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, access: Access, _: Translator, bot: Bot) -> None:
    await cb.answer()
    with contextlib.suppress(Exception):
        await cb.message.delete()
    await _cancel(cb.message, state, session, user, access, _, bot)


@router.callback_query(F.data == "noop")
async def on_noop(cb: CallbackQuery) -> None:
    await cb.answer()


# ------------------------------------------------------------------ staff sign-in


def _locked(telegram_id: int) -> bool:
    q = _login_failures[telegram_id]
    now = time.monotonic()
    while q and now - q[0] > LOGIN_WINDOW:
        q.popleft()
    return len(q) >= LOGIN_MAX_FAILURES


@router.message(Command("login"))
async def cmd_login(message: Message, state: FSMContext, _: Translator, bot: Bot) -> None:
    await drop_screen(bot, message.chat.id, state)
    await state.clear()
    if _locked(message.from_user.id):
        await message.answer(_("login.locked"))
        return
    await state.set_state(LoginStates.username)
    await screen(bot, message.chat.id, state, _("login.username"), kb.cancel_kb(_))


@router.message(LoginStates.username, F.text, ~F.text.startswith("/"))
async def on_login_username(message: Message, state: FSMContext, _: Translator, bot: Bot) -> None:
    await state.update_data(login_username=message.text.strip().lower()[:64])
    await state.set_state(LoginStates.password)
    await screen(bot, message.chat.id, state, _("login.password"), kb.cancel_kb(_))


@router.message(LoginStates.password, F.text, ~F.text.startswith("/"))
async def on_login_password(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    _: Translator,
    settings: Settings,
    bot: Bot,
) -> None:
    password = message.text
    await delete_quietly(bot, message.chat.id, message.message_id)  # never leave a password in the chat
    data = await state.get_data()
    await drop_screen(bot, message.chat.id, state)
    await state.clear()
    if _locked(user.id):
        await message.answer(_("login.locked"))
        return

    account = await repo.get_account_by_username(session, data.get("login_username", ""))
    stored = account.password_hash if account else DUMMY_HASH
    ok = await asyncio.to_thread(verify_password, password, stored)
    if not ok or account is None or not account.is_active:
        _login_failures[user.id].append(time.monotonic())
        await repo.audit(session, repo.tg_actor(user.id), "auth.bot_login_failed", summary=data.get("login_username"))
        await session.commit()
        await message.answer(_("login.failed"))
        return

    _login_failures.pop(user.id, None)
    await repo.link_telegram(session, account, user.id)
    account.last_login_at = utcnow()
    await repo.audit(session, account.username, "auth.bot_login", entity="account", entity_id=account.id)
    await session.commit()
    access = repo.access_for(account, env_admin=user.id in settings.admin_ids)
    await set_user_commands(bot, user.id, user.language, access)
    await show_main_menu(message, session, user, access, _, text=_("login.ok", name=escape(account.label)))


@router.message(Command("logout"))
async def cmd_logout(
    message: Message, state: FSMContext, session: AsyncSession, user: User, _: Translator, settings: Settings, bot: Bot
) -> None:
    await state.clear()
    account = await repo.get_account_by_telegram(session, user.id)
    if account is None:
        await message.answer(_("login.not_logged"))
        return
    account.telegram_id = None
    await repo.audit(session, account.username, "auth.bot_logout", entity="account", entity_id=account.id)
    await session.commit()
    access = repo.access_for(None, env_admin=user.id in settings.admin_ids)
    await set_user_commands(bot, user.id, user.language, access)
    await show_main_menu(message, session, user, access, _, text=_("login.logged_out"))


# ------------------------------------------------------------------ fallback (registered last)

fallback_router = Router(name="fallback")


@fallback_router.message(StateFilter(None))
async def fallback(message: Message, session: AsyncSession, user: User, access: Access, _: Translator) -> None:
    if user.language is None:
        await message.answer(LANGUAGE_PROMPT, reply_markup=kb.language_kb())
        return
    await show_main_menu(message, session, user, access, _, text=_("use_menu"))


@fallback_router.message(F.text.in_(menu_buttons()))
async def menu_button_in_state(message: Message, state: FSMContext, session: AsyncSession, user: User, access: Access, _: Translator, bot: Bot) -> None:
    """A menu button pressed in the middle of a flow: leave the flow."""
    await _cancel(message, state, session, user, access, _, bot)


@fallback_router.message()
async def unexpected_in_state(message: Message, _: Translator) -> None:
    await message.answer(_("err.use_buttons"))


@fallback_router.callback_query()
async def stale_callback(cb: CallbackQuery) -> None:
    await cb.answer()

