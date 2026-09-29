"""Telegram command menus (the '/' button), localized and per role."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from app.db.models import Language
from app.db.repo import Access
from app.i18n import DEFAULT_LANGUAGE, t

log = logging.getLogger(__name__)

STUDENT_COMMANDS = ("start", "language", "help", "cancel")
STAFF_COMMANDS = ("start", "students", "find", "export", "language", "help", "logout", "cancel")
ADMIN_COMMANDS = ("start", "admin", "students", "find", "export", "backup", "language", "help", "logout", "cancel")


def _commands(lang: Language, names: tuple[str, ...]) -> list[BotCommand]:
    return [BotCommand(command=n, description=t(lang, f"cmd.{n}")) for n in names]


async def setup_default_commands(bot: Bot) -> None:
    await bot.set_my_commands(_commands(DEFAULT_LANGUAGE, STUDENT_COMMANDS), scope=BotCommandScopeDefault())
    for lang in Language:
        await bot.set_my_commands(_commands(lang, STUDENT_COMMANDS), scope=BotCommandScopeDefault(), language_code=lang.value)


async def set_user_commands(bot: Bot, chat_id: int, lang: Language | None, access: Access) -> None:
    lang = lang or DEFAULT_LANGUAGE
    names = ADMIN_COMMANDS if access.is_admin else STAFF_COMMANDS if access.is_staff else STUDENT_COMMANDS
    try:
        await bot.set_my_commands(_commands(lang, names), scope=BotCommandScopeChat(chat_id=chat_id))
    except TelegramAPIError as e:  # e.g. the user never opened the bot
        log.debug("Could not set commands for %s: %s", chat_id, e)
