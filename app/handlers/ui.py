"""The bot's 'screen' model: one current screen message per chat.

Each step replaces the previous screen (the old one is deleted), so the chat
stays short and tidy instead of growing into a wall of prompts.
"""

from __future__ import annotations

import contextlib

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from app.i18n import Translator

Markup = InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | None
TOTAL_STEPS = 7


def progress(step: int, total: int = TOTAL_STEPS) -> str:
    return "▰" * step + "▱" * (total - step) + f"  {step}/{total}"


def step_screen(_: Translator, title_key: str, step: int, body: str, tip: str | None = None) -> str:
    text = f"<b>{_(title_key)}</b>\n<code>{progress(step)}</code>\n\n{body}"
    if tip:
        text += f"\n\n<i>{tip}</i>"
    return text


async def forget_screen(state: FSMContext) -> None:
    await state.update_data(screen_id=None)


async def drop_screen(bot: Bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    if prev := data.get("screen_id"):
        with contextlib.suppress(Exception):
            await bot.delete_message(chat_id, prev)
        await state.update_data(screen_id=None)


async def screen(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    text: str,
    markup: Markup = None,
    *,
    photo: str | None = None,
) -> Message:
    """Show a new screen and remove the previous one."""
    data = await state.get_data()
    prev = data.get("screen_id")
    if photo:
        msg = await bot.send_photo(chat_id, photo, caption=text, reply_markup=markup)
    else:
        msg = await bot.send_message(chat_id, text, reply_markup=markup)
    if prev and prev != msg.message_id:
        with contextlib.suppress(Exception):
            await bot.delete_message(chat_id, prev)
    await state.update_data(screen_id=msg.message_id)
    return msg


async def delete_quietly(bot: Bot, chat_id: int, message_id: int | None) -> None:
    if message_id:
        with contextlib.suppress(Exception):
            await bot.delete_message(chat_id, message_id)
