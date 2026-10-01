"""Students send certificates and awards (IELTS, SAT, CEFR, olympiads…).

Steps: type → score / level / description → file(s) → confirm. They are added
during registration (an optional step: kept in the form until it is submitted)
or later from «My certificates». Each one waits for staff to accept it; the
student gets a message with the decision. Accepted certificates are final;
others can be removed by the student.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from html import escape

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app import keyboards as kb
from app.callbacks import CertCb, CertReviewCb
from app.db import repo
from app.db.models import Certificate, CertStatus, CertType, Student, User
from app.db.repo import Access
from app.handlers.common import show_main_menu
from app.handlers.registration import ask as ask_step
from app.handlers.registration import clear_error, say_error
from app.handlers.ui import delete_quietly, drop_screen, screen
from app.i18n import Translator, menu_buttons, t, variants
from app.services import certificates as certs
from app.services.documents import CERTIFICATE_MIMES, FileRejected, extract_file, is_image
from app.services.prefs import Prefs
from app.services.validators import ValidationError
from app.states import CertStates, Registration
from app.views import render_my_certificates

log = logging.getLogger(__name__)
router = Router(name="certificates")

# Albums arrive as several simultaneous updates: handle one file per user at a time.
_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
# Keys of a certificate being added; "in_reg" = added during registration.
CERT_KEYS = {"cert_type": None, "result": None, "files": None, "pages": [], "pages_msg": None, "in_reg": False}


async def in_registration(state: FSMContext) -> bool:
    return bool((await state.get_data()).get("in_reg"))


def cert_title(_: Translator, data: dict) -> str:
    """"🏆 IELTS" while choosing, "🏆 IELTS 7.5" once the result is known."""
    cert_type = CertType(data["cert_type"])
    name = certs.type_label(_.lang, cert_type)
    if result := data.get("result"):
        name += (": " if cert_type in certs.DESCRIBED else " ") + result
    return f"🏆 <b>{escape(name)}</b>"


async def show_list(chat_id: int, student: Student, _: Translator, bot: Bot, *, edit: Message | None = None) -> None:
    text = render_my_certificates(_, student.certificates)
    markup = kb.my_certificates_kb(_, student.certificates)
    if edit is not None:
        try:
            await edit.edit_text(text, reply_markup=markup)
            return
        except Exception:
            pass
    await bot.send_message(chat_id, text, reply_markup=markup)


@router.message(F.text.in_(variants("btn.certificates")))
async def on_my_certificates(
    message: Message, state: FSMContext, session: AsyncSession, user: User, access: Access, _: Translator, bot: Bot
) -> None:
    student = await repo.get_student_by_tg(session, user.id)
    if student is None:  # certificates belong to a registered student
        await show_main_menu(message, session, user, access, _)
        return
    await drop_screen(bot, message.chat.id, state)
    await state.clear()
    await show_list(message.chat.id, student, _, bot)


@router.callback_query(CertCb.filter(F.action == "list"))
async def on_list(cb: CallbackQuery, session: AsyncSession, user: User, _: Translator, bot: Bot) -> None:
    await cb.answer()
    if student := await repo.get_student_by_tg(session, user.id):
        await show_list(cb.message.chat.id, student, _, bot, edit=cb.message)


# ------------------------------------------------------------------ add


@router.callback_query(CertCb.filter(F.action == "add"))
async def on_add(cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, _: Translator, bot: Bot) -> None:
    in_reg = await state.get_state() == Registration.certs.state
    if in_reg:  # keep the registration form; the certificate is added to it
        count = len((await state.get_data()).get("reg_certs") or [])
    else:
        student = await repo.get_student_by_tg(session, user.id)
        if student is None:
            await cb.answer()
            return
        count = len(student.certificates)
    if count >= certs.MAX_PER_STUDENT:
        await cb.answer(_("cert.limit", max=certs.MAX_PER_STUDENT), show_alert=True)
        return
    await cb.answer()
    if in_reg:
        await state.update_data({**CERT_KEYS, "in_reg": True})
    else:
        await drop_screen(bot, cb.message.chat.id, state)
        await state.set_data({"screen_id": cb.message.message_id})  # the list becomes the first screen
    await state.set_state(CertStates.type)
    await screen(bot, cb.message.chat.id, state, _("cert.pick_type"), kb.cert_type_kb(_, back=in_reg))


@router.callback_query(CertCb.filter(F.action == "back"))
async def on_back(cb: CallbackQuery, state: FSMContext, session: AsyncSession, _: Translator, prefs: Prefs, bot: Bot) -> None:
    """Stop adding a certificate during registration: back to the registration step."""
    await cb.answer()
    if not await in_registration(state):
        return
    data = await state.get_data()
    await delete_quietly(bot, cb.message.chat.id, data.get("pages_msg"))
    await state.update_data(**CERT_KEYS)
    await ask_step("certs", cb.message.chat.id, state, session, _, prefs, bot)


@router.callback_query(CertStates.type, CertCb.filter(F.action == "type"))
async def on_type(cb: CallbackQuery, callback_data: CertCb, state: FSMContext, _: Translator, bot: Bot) -> None:
    await cb.answer()
    if callback_data.value not in {c.value for c in CertType}:
        return
    cert_type = CertType(callback_data.value)
    await state.update_data(cert_type=cert_type.value, result=None)
    await state.set_state(CertStates.result)
    data = await state.get_data()
    back = bool(data.get("in_reg"))
    markup = kb.cefr_kb(_, back=back) if cert_type == CertType.CEFR else kb.cert_exit_kb(_, back=back)
    await screen(bot, cb.message.chat.id, state, f"{cert_title(_, data)}\n\n{_(f'cert.ask.{cert_type.value}')}", markup)


async def _save_result(raw: str, message: Message, state: FSMContext, _: Translator, prefs: Prefs, bot: Bot) -> None:
    data = await state.get_data()
    cert_type = CertType(data["cert_type"])
    try:
        result = certs.normalize_result(cert_type, raw)
    except ValidationError as e:
        key = cert_type.value if cert_type in certs.SCORES else e.key
        await say_error(message, state, _(f"cert.err.{key}"), bot)
        return
    await clear_error(message.chat.id, state, bot)
    await state.update_data(result=result, pages=[], pages_msg=None, files=None)
    await state.set_state(CertStates.files)
    data = await state.get_data()
    body = f"{cert_title(_, data)}\n\n{_('cert.ask_files', max=prefs.max_document_pages)}"
    await screen(bot, message.chat.id, state, body, kb.cert_exit_kb(_, back=bool(data.get("in_reg"))))


@router.message(CertStates.result, F.text, ~F.text.startswith("/"), ~F.text.in_(menu_buttons()))
async def on_result_text(message: Message, state: FSMContext, _: Translator, prefs: Prefs, bot: Bot) -> None:
    await _save_result(message.text, message, state, _, prefs, bot)


@router.callback_query(CertStates.result, CertCb.filter(F.action == "result"))
async def on_result_button(cb: CallbackQuery, callback_data: CertCb, state: FSMContext, _: Translator, prefs: Prefs, bot: Bot) -> None:
    await cb.answer()
    await _save_result(callback_data.value, cb.message, state, _, prefs, bot)


@router.message(CertStates.result, ~F.text)
async def on_result_other(message: Message, state: FSMContext, _: Translator, bot: Bot) -> None:
    await say_error(message, state, _("cert.err.type_text"), bot)


# ------------------------------------------------------------------ files


@router.message(CertStates.files, F.photo | F.document)
async def on_file(message: Message, state: FSMContext, user: User, _: Translator, prefs: Prefs, bot: Bot) -> None:
    try:
        file = extract_file(message, CERTIFICATE_MIMES)
    except FileRejected as e:
        await say_error(message, state, _("cert.err.file_type" if e.code == "type" else f"file_err.{e.code}"), bot)
        return
    async with _locks[user.id]:
        if await state.get_state() != CertStates.files.state:
            return  # a late photo of an album; the first ones already moved on
        data = await state.get_data()
        pages: list[dict] = data.get("pages") or []
        if not is_image(file):  # a PDF is the whole certificate
            if pages:
                await say_error(message, state, _("cert.err.pdf_after_photos"), bot)
                return
            await state.update_data(files=[file], pages=[])
            await show_confirm(message.chat.id, state, _, bot)
            return
        if len(pages) >= prefs.max_document_pages:
            await say_error(message, state, _("reg.max_pages", max=prefs.max_document_pages), bot)
            return
        pages.append(file)
        await state.update_data(pages=pages)
        text = _("reg.page_added", n=len(pages))
        markup = kb.cert_pages_kb(_, back=bool(data.get("in_reg")))
        if msg_id := data.get("pages_msg"):
            try:
                await bot.edit_message_text(text, chat_id=message.chat.id, message_id=msg_id, reply_markup=markup)
                return
            except Exception:
                pass
        msg = await message.answer(text, reply_markup=markup)
        await state.update_data(pages_msg=msg.message_id)


@router.callback_query(CertStates.files, CertCb.filter(F.action == "done"))
async def on_files_done(cb: CallbackQuery, state: FSMContext, user: User, _: Translator, bot: Bot) -> None:
    async with _locks[user.id]:
        pages = (await state.get_data()).get("pages") or []
        if not pages:
            await cb.answer(_("err.no_pages"), show_alert=True)
            return
        await state.update_data(files=pages, pages=[], pages_msg=None)
    await cb.answer()
    await delete_quietly(bot, cb.message.chat.id, cb.message.message_id)
    await show_confirm(cb.message.chat.id, state, _, bot)


@router.message(CertStates.files)
async def on_file_other(message: Message, state: FSMContext, _: Translator, bot: Bot) -> None:
    await say_error(message, state, _("cert.ask_files_short"), bot)


async def show_confirm(chat_id: int, state: FSMContext, _: Translator, bot: Bot) -> None:
    await clear_error(chat_id, state, bot)
    await state.set_state(CertStates.confirm)
    data = await state.get_data()
    in_reg = bool(data.get("in_reg"))
    question = _("cert.confirm_reg") if in_reg else _("cert.confirm")
    body = f"{cert_title(_, data)}\n{_('cert.files', n=len(data['files']))}\n\n{question}"
    await screen(bot, chat_id, state, body, kb.cert_confirm_kb(_, back=in_reg))


# ------------------------------------------------------------------ submit


@router.callback_query(CertStates.confirm, CertCb.filter(F.action == "submit"))
async def on_submit(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, _: Translator, prefs: Prefs, bot: Bot
) -> None:
    data = await state.get_data()
    if data.get("in_reg") and data.get("files") and data.get("result"):
        # During registration: into the form; saved with the student on «Submit».
        item = {"type": data["cert_type"], "result": data["result"], "files": data["files"]}
        await state.update_data(reg_certs=[*(data.get("reg_certs") or []), item], **CERT_KEYS)
        await cb.answer(_("cert.added"))
        await ask_step("certs", cb.message.chat.id, state, session, _, prefs, bot)
        return
    student = await repo.get_student_by_tg(session, user.id)
    if student is None or not data.get("files") or not data.get("result"):
        await cb.answer()
        await drop_screen(bot, cb.message.chat.id, state)
        await state.clear()
        return
    if len(student.certificates) >= certs.MAX_PER_STUDENT:
        await cb.answer(_("cert.limit", max=certs.MAX_PER_STUDENT), show_alert=True)
        return
    await cb.answer()
    cert = await repo.add_certificate(session, student, CertType(data["cert_type"]), data["result"], data["files"])
    await repo.audit(
        session, repo.tg_actor(user.id), "certificate.submit", entity="student", entity_id=student.id,
        summary=f"{certs.label('en', cert)} · {student.full_name}",
    )
    await session.commit()
    await drop_screen(bot, cb.message.chat.id, state)
    await state.clear()
    log.info("Student %s sent a certificate (%s)", user.id, cert.type.value)

    await bot.send_message(cb.message.chat.id, _("cert.sent"))
    await show_list(cb.message.chat.id, student, _, bot)
    if prefs.notify_leaders:
        await _notify_leaders(bot, session, student, cert)


async def _notify_leaders(bot: Bot, session: AsyncSession, student: Student, cert: Certificate) -> None:
    for tg_id in await repo.leader_telegram_ids(session, student.group_id):
        if tg_id == student.telegram_id:
            continue
        leader = await session.get(User, tg_id)
        lang = leader.language if leader else None
        text = t(lang, "cert.notify_new", name=escape(student.full_name), group=escape(student.group.name), cert=escape(certs.label(lang, cert)))
        button = InlineKeyboardButton(text=t(lang, "btn.cert_open"), callback_data=CertReviewCb(action="open", id=cert.id).pack())
        try:
            await bot.send_message(tg_id, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]))
        except Exception as e:  # blocked the bot, etc.
            log.debug("Could not notify leader %s: %s", tg_id, e)


# ------------------------------------------------------------------ remove


def _own(student: Student | None, cert_id: int):
    return next((c for c in student.certificates if c.id == cert_id), None) if student else None


@router.callback_query(CertCb.filter(F.action == "del"))
async def on_delete(cb: CallbackQuery, callback_data: CertCb, session: AsyncSession, user: User, _: Translator) -> None:
    cert = _own(await repo.get_student_by_tg(session, user.id), callback_data.id)
    if cert is None or cert.status == CertStatus.APPROVED:
        await cb.answer(_("cert.cannot_delete"), show_alert=True)
        return
    await cb.answer()
    await cb.message.edit_text(
        _("cert.delete_confirm", cert=escape(certs.label(_.lang, cert))),
        reply_markup=kb.confirm_kb(_, yes=CertCb(action="del_ok", id=cert.id).pack(), no=CertCb(action="list").pack()),
    )


@router.callback_query(CertCb.filter(F.action == "del_ok"))
async def on_delete_ok(cb: CallbackQuery, callback_data: CertCb, session: AsyncSession, user: User, _: Translator, bot: Bot) -> None:
    student = await repo.get_student_by_tg(session, user.id)
    cert = _own(student, callback_data.id)
    if cert is None or cert.status == CertStatus.APPROVED:
        await cb.answer(_("cert.cannot_delete"), show_alert=True)
        return
    student.certificates.remove(cert)  # delete-orphan
    await repo.audit(
        session, repo.tg_actor(user.id), "certificate.delete", entity="student", entity_id=student.id,
        summary=f"{certs.label('en', cert)} · {student.full_name}",
    )
    await session.commit()
    await cb.answer(_("cert.deleted"))
    await show_list(cb.message.chat.id, student, _, bot, edit=cb.message)
