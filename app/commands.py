"""Telegram command menus (the '/' button) and the bot's profile texts, localized."""

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


async def setup_profile(bot: Bot) -> None:
    """Name, short description ("About") and description ("What can this bot do?")
    in every language; the default is shown to users of other languages.

    Only changed values are sent: Telegram rate-limits these calls heavily.
    """
    for lang in (None, *Language):
        texts = lambda key: t(lang or DEFAULT_LANGUAGE, key)  # noqa: E731
        code = lang.value if lang else None
        try:
            if (await bot.get_my_name(language_code=code)).name != texts("bot.name"):
                await bot.set_my_name(name=texts("bot.name"), language_code=code)
            if (await bot.get_my_short_description(language_code=code)).short_description != texts("bot.short_description"):
                await bot.set_my_short_description(short_description=texts("bot.short_description"), language_code=code)
            if (await bot.get_my_description(language_code=code)).description != texts("bot.description"):
                await bot.set_my_description(description=texts("bot.description"), language_code=code)
        except TelegramAPIError as e:  # e.g. "Too Many Requests": try again at the next start
            log.warning("Could not update the bot profile (%s): %s", code or "default", e)
            return


async def set_user_commands(bot: Bot, chat_id: int, lang: Language | None, access: Access) -> None:
    lang = lang or DEFAULT_LANGUAGE
    names = ADMIN_COMMANDS if access.is_admin else STAFF_COMMANDS if access.is_staff else STUDENT_COMMANDS
    try:
        await bot.set_my_commands(_commands(lang, names), scope=BotCommandScopeChat(chat_id=chat_id))
    except TelegramAPIError as e:  # e.g. the user never opened the bot
        log.debug("Could not set commands for %s: %s", chat_id, e)
