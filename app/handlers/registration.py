"""Student registration.

Steps: document (read on the server) → check the read data → phone → group →
3x4 photo → CV → permanent address → temporary address (optional) → school
certificate → form 086 (optional) → certificates (optional) → review. Each step
is one screen; the previous screen is removed, so the chat stays short.

Registered students can later send documents they are missing (e.g. ones added
to the form after they registered) from «My profile».
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import date
from html import escape
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from app import keyboards as kb
from app.callbacks import CertCb, DocCb, EditFieldCb, GroupPickCb, RegCb
from app.config import Settings
from app.db import repo
from app.db.models import OPTIONAL_DOCUMENTS, CertType, DocType, DocumentKind, Gender, Group, Student, User
from app.db.repo import Access, StudentForm
from app.handlers.common import show_main_menu
from app.handlers.ui import delete_quietly, drop_screen, screen, step_screen
from app.i18n import Translator, t, variants
from app.services import certificates as certs
from app.services import vision
from app.services.documents import PAGED, FileRejected, download, extract_file, is_image
from app.services.prefs import Prefs
from app.services.validators import (
    ValidationError,
    age_on,
    format_phone,
    normalize_name_part,
    normalize_phone,
    pretty_name,
)
from app.states import MyDocuments, Registration
from app.views import render_check, render_profile, render_review

log = logging.getLogger(__name__)
router = Router(name="registration")

# Steps that take a document as a PDF or photos of its pages; each is named after its DocumentKind.
FILE_STEPS = tuple(kind.value for kind in PAGED)
ORDER = ("document", "phone", "group", "photo", *FILE_STEPS, "certs")
STEP_NO = {"document": 1, "check": 2} | {step: n for n, step in enumerate(ORDER[1:], start=3)}
OPTIONAL = {kind.value for kind in OPTIONAL_DOCUMENTS} | {"certs"}
# The form key that is set once a step is done. Optional steps must still be passed once.
REQUIRED = {"document": "doc", "phone": "phone", "group": "group_id", "photo": "photo_files"} | {
    step: f"{step}_done" if step in OPTIONAL else f"{step}_files" for step in (*FILE_STEPS, "certs")
}
FILE_STATES = tuple(getattr(Registration, step) for step in FILE_STEPS)
# Albums arrive as several simultaneous updates: handle one file per user at a time.
_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


# ------------------------------------------------------------------ helpers


async def say_error(message: Message, state: FSMContext, text: str, bot: Bot) -> None:
    """Show an error, replacing the previous error instead of piling them up."""
    data = await state.get_data()
    await delete_quietly(bot, message.chat.id, data.get("error_id"))
    err = await message.reply(text)
    await state.update_data(error_id=err.message_id)


async def clear_error(chat_id: int, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    await delete_quietly(bot, chat_id, data.get("error_id"))
    await state.update_data(error_id=None)


async def ask(field: str, chat_id: int, state: FSMContext, session: AsyncSession, _: Translator, prefs: Prefs, bot: Bot) -> None:
    """Show the screen for ``field`` and switch to its state."""
    await clear_error(chat_id, state, bot)
    step = STEP_NO[field]
    if field == "document":
        await state.set_state(Registration.document)
        body, markup, tip = _("reg.document"), kb.cancel_kb(_), _("reg.document_tip")
        await screen(bot, chat_id, state, step_screen(_, "step.document", step, body, tip), markup)
    elif field == "phone":
        await state.set_state(Registration.phone)
        await screen(bot, chat_id, state, step_screen(_, "step.phone", step, _("reg.phone")), kb.phone_kb(_))
    elif field == "group":
        groups = await repo.list_groups(session)
        if not groups:
            await drop_screen(bot, chat_id, state)
            await state.clear()
            await bot.send_message(chat_id, _("err.no_groups"))
            return
        await state.set_state(Registration.group)
        await screen(bot, chat_id, state, step_screen(_, "step.group", step, _("reg.group")), kb.group_pick_kb(_, groups))
    elif field == "photo":
        await state.set_state(Registration.photo)
        body = step_screen(_, "step.photo", step, _("reg.photo"), _("reg.photo_tip"))
        await screen(bot, chat_id, state, body, kb.cancel_kb(_))
    elif field in FILE_STEPS:
        await state.set_state(getattr(Registration, field))
        await state.update_data(pages=[], pages_msg=None)
        body = step_screen(_, f"step.{field}", step, _(f"reg.{field}", max=prefs.max_document_pages))
        markup = kb.skip_kb(_, RegCb(action="skip").pack()) if field in OPTIONAL else kb.cancel_kb(_)
        await screen(bot, chat_id, state, body, markup)
    elif field == "certs":
        await state.set_state(Registration.certs)
        items = (await state.get_data()).get("reg_certs") or []
        body = _("reg.certs")
        if items:
            added = "\n".join(f"✅ {escape(certs.describe(_.lang, c['type'], c.get('result')))}" for c in items)
            body += "\n\n" + _("reg.certs_added", list=added)
        await screen(bot, chat_id, state, step_screen(_, "step.certs", step, body), kb.reg_certs_kb(_, items))


async def advance(done: str, chat_id: int, state: FSMContext, session: AsyncSession, _: Translator, prefs: Prefs, bot: Bot) -> None:
    """Next missing step, or back to the review when editing."""
    data = await state.get_data()
    if data.get("editing"):
        missing = next((f for f in ORDER if not data.get(REQUIRED[f])), None)
        if missing:
            await ask(missing, chat_id, state, session, _, prefs, bot)
        else:
            await show_review(chat_id, state, _, bot)
        return
    index = ORDER.index(done)
    if index + 1 < len(ORDER):
        await ask(ORDER[index + 1], chat_id, state, session, _, prefs, bot)
    else:
        await show_review(chat_id, state, _, bot)


async def show_check(chat_id: int, state: FSMContext, _: Translator, bot: Bot) -> None:
    await clear_error(chat_id, state, bot)
    await state.set_state(Registration.check)
    data = await state.get_data()
    body = step_screen(_, "step.check", 2, render_check(_, data), _("reg.check_tip"))
    await screen(bot, chat_id, state, body, kb.check_kb(_))


async def show_review(chat_id: int, state: FSMContext, _: Translator, bot: Bot) -> None:
    await clear_error(chat_id, state, bot)
    await state.set_state(Registration.review)
    await state.update_data(editing=True)
    data = await state.get_data()
    photo = next((f["file_id"] for f in data.get("photo_files") or [] if f["type"] == "photo"), None)
    await screen(bot, chat_id, state, render_review(_, data), kb.review_kb(_), photo=photo)


async def go_back(chat_id: int, state: FSMContext, _: Translator, bot: Bot) -> None:
    """Back to the screen a field was edited from."""
    data = await state.get_data()
    if data.get("back_to") == "review":
        await show_review(chat_id, state, _, bot)
    else:
        await show_check(chat_id, state, _, bot)


def current_value(data: dict, field: str) -> str | None:
    return data.get("middle_name") if field == "middle_name" else (data.get("doc") or {}).get(field)


def as_read(doc: dict, middle_name: str | None) -> dict:
    """Values as they came from the document, to show staff what the student changed."""
    return {"last_name": doc["last_name"], "first_name": doc["first_name"], "middle_name": middle_name, "gender": doc["gender"]}


def corrections(data: dict) -> dict | None:
    """{field: [read, final]} for every value the student changed by hand."""
    read = data.get("read") or {}
    changes = {
        field: [before, current_value(data, field)]
        for field, before in read.items()
        if before and before != current_value(data, field)
    }
    return changes or None


async def ask_name_part(chat_id: int, state: FSMContext, _: Translator, bot: Bot, field: str, back_to: str) -> None:
    """Let the student type a surname, name or patronymic by hand."""
    await clear_error(chat_id, state, bot)
    await state.set_state(Registration.name_part)
    await state.update_data(name_field=field, back_to=back_to)
    data = await state.get_data()
    current = current_value(data, field)
    if current:
        body, markup = _("reg.type_field", field=_(f"sfield.{field}"), current=escape(current)), kb.back_kb(_)
    else:  # the patronymic wasn't readable on the document: it must be typed
        body, markup = _("reg.patronymic"), kb.cancel_kb(_)
    # Many foreign documents have no patronymic at all; Uzbek ones always do.
    if field == "middle_name" and (data.get("doc") or {}).get("issuing_state", "UZB") != "UZB":
        markup = kb.no_patronymic_kb(_, back=bool(current) or data.get("no_patronymic") or back_to == "review")
    text = step_screen(_, "step.check", 2, body) if back_to == "check" else body
    await screen(bot, chat_id, state, text, markup)


# ------------------------------------------------------------------ entry points


async def tell_locked(message: Message, session: AsyncSession, user: User, access: Access, _: Translator) -> None:
    """Submitted data is final for the student: only staff can correct it."""
    await show_main_menu(message, session, user, access, _, text=_("reg.locked"))


@router.message(F.text.in_(variants("btn.register")))
async def on_register_button(message: Message, session: AsyncSession, user: User, access: Access, _: Translator) -> None:
    if await repo.get_student_by_tg(session, user.id):
        await tell_locked(message, session, user, access, _)
        return
    await message.answer(_("welcome.new"), reply_markup=kb.consent_kb(_))


# Menus sent before data was locked still have this button.
@router.message(F.text.in_(variants("btn.update")))
async def on_update_button(message: Message, session: AsyncSession, user: User, access: Access, _: Translator) -> None:
    await tell_locked(message, session, user, access, _)


@router.callback_query(RegCb.filter(F.action == "consent"))
async def on_consent(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, access: Access, _: Translator, prefs: Prefs, bot: Bot
) -> None:
    if not prefs.registration_open:
        await cb.answer(_("reg.closed"), show_alert=True)
        return
    await cb.answer()
    await cb.message.edit_reply_markup(reply_markup=None)
    if await repo.get_student_by_tg(session, user.id):  # an old "Agree" button
        await tell_locked(cb.message, session, user, access, _)
        return
    await state.set_data({})
    # Remove the menu keyboard while the form is open; buttons are inline.
    note = await cb.message.answer("📝", reply_markup=ReplyKeyboardRemove())
    await delete_quietly(bot, cb.message.chat.id, note.message_id)
    await ask("document", cb.message.chat.id, state, session, _, prefs, bot)


@router.message(F.text.in_(variants("btn.profile")))
async def on_profile(message: Message, session: AsyncSession, user: User, access: Access, _: Translator, settings: Settings) -> None:
    student = await repo.get_student_by_tg(session, user.id)
    if student is None:
        await show_main_menu(message, session, user, access, _)
        return
    text = render_profile(_, student, ZoneInfo(settings.timezone))
    missing = missing_documents(student)
    markup = kb.add_documents_kb(_, missing) if missing else None
    if missing:
        text += "\n\n" + _("mydocs.missing")
    photo = student.document(DocumentKind.PHOTO)
    file = photo.files[0] if photo and photo.files else None
    if file and file["type"] == "photo":
        await message.answer_photo(file["file_id"], caption=text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


# ------------------------------------------------------------------ 1. document


@router.message(Registration.document, F.photo | F.document)
async def on_document(
    message: Message, state: FSMContext, session: AsyncSession, user: User, _: Translator, prefs: Prefs, bot: Bot
) -> None:
    async with _locks[user.id]:
        if await state.get_state() != Registration.document.state:
            return  # a second photo of an album; the first one already moved on
        try:
            file = extract_file(message, DocumentKind.PASSPORT)
        except FileRejected as e:
            await say_error(message, state, _("doc_err.not_image" if e.code != "size" else "file_err.size"), bot)
            return
        status = await message.answer(_("reg.reading"))
        try:
            result = await vision.read_document(await download(bot, file["file_id"]))
        finally:
            await delete_quietly(bot, message.chat.id, status.message_id)
        if result.error:
            await say_error(message, state, _(f"doc_err.{result.error}"), bot)
            return

        mrz = result.mrz
        age = age_on(mrz.birth_date, date.today())
        if not prefs.min_student_age <= age <= prefs.max_student_age:
            await say_error(message, state, _("doc_err.age"), bot)
            return
        duplicate = await repo.find_duplicate_document(
            session, pinfl=mrz.pinfl, doc_number=mrz.document_number, telegram_id=user.id
        )
        if duplicate is not None:
            log.warning("Document %s already registered by another Telegram account", mrz.document_number)
            await say_error(message, state, _("doc_err.duplicate"), bot)
            return

        is_id = not mrz.is_passport
        needs_front = mrz.needs_front  # TD2 cards have the photo on the MRZ side
        doc = {
            "last_name": pretty_name(mrz.last_name),
            "first_name": pretty_name(mrz.first_name),
            "birth_date": mrz.birth_date.isoformat(),
            "gender": mrz.sex or Gender.MALE.value,
            "doc_type": (DocType.ID_CARD if is_id else DocType.PASSPORT).value,
            "doc_number": mrz.document_number,
            "doc_expiry": mrz.expiry_date.isoformat(),
            "pinfl": mrz.pinfl,
            "nationality": mrz.nationality,
            "issuing_state": mrz.issuing_state,
        }
        await state.update_data(
            doc=doc,
            read=as_read(doc, result.patronymic),
            passport_files=[{**file, "side": "back" if needs_front else "main"}],
            middle_name=result.patronymic,
            no_patronymic=False,
        )
        await clear_error(message.chat.id, state, bot)
        if needs_front:
            await state.set_state(Registration.id_front)
            await screen(bot, message.chat.id, state, step_screen(_, "step.document", 1, _("reg.id_front")), kb.cancel_kb(_))
            return
        await after_document(message.chat.id, state, _, bot)


async def after_document(chat_id: int, state: FSMContext, _: Translator, bot: Bot) -> None:
    data = await state.get_data()
    if not data.get("middle_name") and not data.get("no_patronymic"):
        await ask_name_part(chat_id, state, _, bot, "middle_name", "check")
    else:
        await show_check(chat_id, state, _, bot)


@router.message(Registration.id_front, F.photo | F.document)
async def on_id_front(message: Message, state: FSMContext, user: User, _: Translator, bot: Bot) -> None:
    async with _locks[user.id]:
        if await state.get_state() != Registration.id_front.state:
            return
        try:
            file = extract_file(message, DocumentKind.PASSPORT)
        except FileRejected as e:
            await say_error(message, state, _("doc_err.not_image" if e.code != "size" else "file_err.size"), bot)
            return
        status = await message.answer(_("reg.checking"))
        try:
            error, patronymic = await vision.check_id_front(await download(bot, file["file_id"]))
        finally:
            await delete_quietly(bot, message.chat.id, status.message_id)
        if error:
            await say_error(message, state, _("doc_err.front" if error == "no_face" else f"doc_err.{error}"), bot)
            return
        data = await state.get_data()
        files = [f for f in data.get("passport_files") or [] if f.get("side") != "front"]
        if not vision.prints_patronymic(data["doc"].get("issuing_state", "UZB")):
            patronymic = None
        middle_name = data.get("middle_name") or patronymic
        await state.update_data(
            passport_files=[*files, {**file, "side": "front"}],
            middle_name=middle_name,
            read=as_read(data["doc"], middle_name),
        )
        await after_document(message.chat.id, state, _, bot)


@router.message(Registration.document)
@router.message(Registration.id_front)
async def on_document_other(message: Message, state: FSMContext, _: Translator, bot: Bot) -> None:
    await say_error(message, state, _("doc_err.not_image"), bot)


# ------------------------------------------------------------------ 2. check & fix


@router.message(Registration.name_part, F.text)
async def on_name_part(message: Message, state: FSMContext, _: Translator, bot: Bot) -> None:
    try:
        value = normalize_name_part(message.text)
    except ValidationError:
        await say_error(message, state, _("err.name_part"), bot)
        return
    data = await state.get_data()
    field = data.get("name_field") or "middle_name"
    if field == "middle_name":
        await state.update_data(middle_name=value, no_patronymic=False)
    else:
        await state.update_data(doc={**data["doc"], field: value})
    await go_back(message.chat.id, state, _, bot)


@router.callback_query(Registration.name_part, RegCb.filter(F.action == "no_middle"))
async def on_no_patronymic(cb: CallbackQuery, state: FSMContext, _: Translator, bot: Bot) -> None:
    await cb.answer()
    data = await state.get_data()
    if (data.get("doc") or {}).get("issuing_state", "UZB") == "UZB":
        return
    await state.update_data(middle_name=None, no_patronymic=True)
    await go_back(cb.message.chat.id, state, _, bot)


@router.message(Registration.name_part)
async def on_name_part_other(message: Message, state: FSMContext, _: Translator, bot: Bot) -> None:
    await say_error(message, state, _("err.name_part"), bot)


@router.callback_query(Registration.check, RegCb.filter(F.action == "correct"))
async def on_check_ok(cb: CallbackQuery, state: FSMContext, session: AsyncSession, _: Translator, prefs: Prefs, bot: Bot) -> None:
    await cb.answer()
    await advance("document", cb.message.chat.id, state, session, _, prefs, bot)


@router.callback_query(Registration.check, RegCb.filter(F.action == "retake"))
async def on_check_retake(cb: CallbackQuery, state: FSMContext, session: AsyncSession, _: Translator, prefs: Prefs, bot: Bot) -> None:
    await cb.answer()
    await ask("document", cb.message.chat.id, state, session, _, prefs, bot)


@router.callback_query(Registration.check, EditFieldCb.filter())
@router.callback_query(Registration.review, EditFieldCb.filter())
async def on_edit_field(
    cb: CallbackQuery, callback_data: EditFieldCb, state: FSMContext, session: AsyncSession, _: Translator, prefs: Prefs, bot: Bot
) -> None:
    field, chat_id = callback_data.field, cb.message.chat.id
    back_to = "review" if await state.get_state() == Registration.review.state else "check"
    await cb.answer()
    if field in kb.NAME_FIELDS:
        await ask_name_part(chat_id, state, _, bot, field, back_to)
    elif field == "gender" and not callback_data.value:
        await cb.message.edit_reply_markup(reply_markup=kb.reg_gender_kb(_))
    elif field == "gender" and callback_data.value in {g.value for g in Gender}:
        data = await state.get_data()
        await state.update_data(doc={**data["doc"], "gender": callback_data.value}, back_to=back_to)
        await go_back(chat_id, state, _, bot)
    elif back_to == "review" and field in ORDER:
        await ask(field, chat_id, state, session, _, prefs, bot)


@router.callback_query(Registration.check, RegCb.filter(F.action == "return"))
async def on_check_return(cb: CallbackQuery, _: Translator) -> None:
    await cb.answer()
    await cb.message.edit_reply_markup(reply_markup=kb.check_kb(_))


@router.callback_query(Registration.review, RegCb.filter(F.action == "return"))
async def on_review_return(cb: CallbackQuery, _: Translator) -> None:
    await cb.answer()
    await cb.message.edit_reply_markup(reply_markup=kb.edit_fields_kb(_))


@router.callback_query(Registration.name_part, RegCb.filter(F.action == "return"))
async def on_name_part_return(cb: CallbackQuery, state: FSMContext, _: Translator, bot: Bot) -> None:
    await cb.answer()
    await go_back(cb.message.chat.id, state, _, bot)


# ------------------------------------------------------------------ 3. phone


@router.message(Registration.phone, F.contact)
async def on_contact(message: Message, state: FSMContext, session: AsyncSession, _: Translator, prefs: Prefs, bot: Bot) -> None:
    contact = message.contact
    if contact.user_id != message.from_user.id:
        await say_error(message, state, _("err.foreign_contact"), bot)
        return
    raw = contact.phone_number
    await _save_phone(raw if raw.startswith("+") else "+" + raw, message, state, session, _, prefs, bot)


@router.message(Registration.phone, F.text, ~F.text.in_(variants("btn.cancel")))
async def on_phone_text(message: Message, state: FSMContext, session: AsyncSession, _: Translator, prefs: Prefs, bot: Bot) -> None:
    await _save_phone(message.text, message, state, session, _, prefs, bot)


async def _save_phone(raw: str, message: Message, state: FSMContext, session: AsyncSession, _: Translator, prefs: Prefs, bot: Bot) -> None:
    try:
        phone = normalize_phone(raw)
    except ValidationError:
        await say_error(message, state, _("err.phone"), bot)
        return
    await state.update_data(phone=phone)
    await clear_error(message.chat.id, state, bot)
    # This message also removes the "share contact" keyboard.
    await message.answer(f"📱 {format_phone(phone)}  ✅", reply_markup=ReplyKeyboardRemove())
    await advance("phone", message.chat.id, state, session, _, prefs, bot)


# ------------------------------------------------------------------ 4. group


@router.callback_query(Registration.group, GroupPickCb.filter(F.action == "prog"))
async def on_group_program(cb: CallbackQuery, callback_data: GroupPickCb, session: AsyncSession, _: Translator) -> None:
    await cb.answer()
    await cb.message.edit_reply_markup(reply_markup=kb.group_pick_kb(_, await repo.list_groups(session), callback_data.program))


@router.callback_query(Registration.group, GroupPickCb.filter(F.action == "pick"))
async def on_group_pick(cb: CallbackQuery, callback_data: GroupPickCb, state: FSMContext, session: AsyncSession, _: Translator, prefs: Prefs, bot: Bot) -> None:
    group = await session.get(Group, callback_data.group_id)
    await cb.answer(group.name if group else None)
    if group is None or not group.is_active:
        return
    await state.update_data(group_id=group.id, group_name=group.name)
    await advance("group", cb.message.chat.id, state, session, _, prefs, bot)


@router.message(Registration.group, F.text)
async def on_group_text(message: Message, state: FSMContext, session: AsyncSession, _: Translator, prefs: Prefs, bot: Bot) -> None:
    query = "-".join(message.text.upper().split())
    groups = await repo.list_groups(session)
    compact = query.replace("-", "")
    matches = [g for g in groups if g.name.upper() == query] or [
        g for g in groups if compact and compact in g.name.upper().replace("-", "")
    ]
    if len(matches) == 1:
        await state.update_data(group_id=matches[0].id, group_name=matches[0].name)
        await advance("group", message.chat.id, state, session, _, prefs, bot)
        return
    if not matches:
        await say_error(message, state, _("err.group_not_found", query=escape(message.text[:40])), bot)
        return
    await screen(bot, message.chat.id, state, step_screen(_, "step.group", 4, _("reg.group")), kb.group_pick_kb(_, matches))


# ------------------------------------------------------------------ 5. 3x4 photo


@router.message(Registration.photo, F.photo | F.document)
async def on_photo(message: Message, state: FSMContext, session: AsyncSession, user: User, _: Translator, prefs: Prefs, bot: Bot) -> None:
    async with _locks[user.id]:
        if await state.get_state() != Registration.photo.state:
            return
        try:
            file = extract_file(message, DocumentKind.PHOTO)
        except FileRejected as e:
            await say_error(message, state, _("photo_err.not_image" if e.code != "size" else "file_err.size"), bot)
            return
        status = await message.answer(_("reg.checking"))
        try:
            error = await vision.check_portrait(await download(bot, file["file_id"]))
        finally:
            await delete_quietly(bot, message.chat.id, status.message_id)
        if error:
            await say_error(message, state, _(f"photo_err.{error}"), bot)
            return
        await state.update_data(photo_files=[file])
        await advance("photo", message.chat.id, state, session, _, prefs, bot)


@router.message(Registration.photo)
async def on_photo_other(message: Message, state: FSMContext, _: Translator, bot: Bot) -> None:
    await say_error(message, state, _("photo_err.not_image"), bot)


# ------------------------------------------------------------------ 6–10. CV and other documents


def file_step(state_name: str | None) -> str | None:
    return next((step for step, st in zip(FILE_STEPS, FILE_STATES) if st.state == state_name), None)


async def collect_page(message: Message, state: FSMContext, file: dict, _: Translator, prefs: Prefs, bot: Bot) -> list[dict] | None:
    """One file of a document: a PDF or Word file is the whole document and is
    returned; photos are its pages, collected until «Done» (None until then)."""
    data = await state.get_data()
    pages: list[dict] = data.get("pages") or []
    if not is_image(file):
        if pages:  # a file after photos: keep the photos, ignore the file
            await say_error(message, state, _("file_err.type"), bot)
            return None
        await state.update_data(pages=[])
        return [file]
    if len(pages) >= prefs.max_document_pages:
        await say_error(message, state, _("reg.max_pages", max=prefs.max_document_pages), bot)
        return None
    pages.append(file)
    await state.update_data(pages=pages)
    text = _("reg.page_added", n=len(pages))
    if msg_id := data.get("pages_msg"):
        try:
            await bot.edit_message_text(text, chat_id=message.chat.id, message_id=msg_id, reply_markup=kb.pages_kb(_))
            return None
        except Exception:
            pass
    msg = await message.answer(text, reply_markup=kb.pages_kb(_))
    await state.update_data(pages_msg=msg.message_id)
    return None


def file_error(e: FileRejected, kind: DocumentKind) -> str:
    if e.code == "type" and kind != DocumentKind.CV:
        return "file_err.pdf_or_photo"
    return f"file_err.{e.code}"


@router.message(StateFilter(*FILE_STATES), F.photo | F.document)
async def on_file(message: Message, state: FSMContext, session: AsyncSession, user: User, _: Translator, prefs: Prefs, bot: Bot) -> None:
    step = file_step(await state.get_state())
    try:
        file = extract_file(message, DocumentKind(step))
    except FileRejected as e:
        await say_error(message, state, _(file_error(e, DocumentKind(step))), bot)
        return
    async with _locks[user.id]:
        if file_step(await state.get_state()) != step:
            return  # a late photo of an album; the first ones already moved on
        files = await collect_page(message, state, file, _, prefs, bot)
        if files:
            await state.update_data({f"{step}_files": files, f"{step}_done": True})
            await advance(step, message.chat.id, state, session, _, prefs, bot)


@router.callback_query(StateFilter(*FILE_STATES), RegCb.filter(F.action == "done"))
async def on_pages_done(cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, _: Translator, prefs: Prefs, bot: Bot) -> None:
    step = file_step(await state.get_state())
    async with _locks[user.id]:
        pages = (await state.get_data()).get("pages") or []
        if not pages:
            await cb.answer(_("err.no_pages"), show_alert=True)
            return
        await state.update_data({f"{step}_files": pages, f"{step}_done": True, "pages": [], "pages_msg": None})
    await cb.answer()
    await delete_quietly(bot, cb.message.chat.id, cb.message.message_id)
    await advance(step, cb.message.chat.id, state, session, _, prefs, bot)


@router.callback_query(StateFilter(*FILE_STATES), RegCb.filter(F.action == "skip"))
async def on_file_skip(cb: CallbackQuery, state: FSMContext, session: AsyncSession, _: Translator, prefs: Prefs, bot: Bot) -> None:
    """Optional documents: skipping one (also from the review) leaves it out."""
    step = file_step(await state.get_state())
    await cb.answer()
    if step not in OPTIONAL:
        return
    data = await state.get_data()
    await delete_quietly(bot, cb.message.chat.id, data.get("pages_msg"))
    await state.update_data({f"{step}_files": None, f"{step}_done": True, "pages": [], "pages_msg": None})
    await advance(step, cb.message.chat.id, state, session, _, prefs, bot)


@router.message(StateFilter(*FILE_STATES))
async def on_file_other(message: Message, state: FSMContext, _: Translator, bot: Bot) -> None:
    await say_error(message, state, _("file_err.expected"), bot)


# ------------------------------------------------------------------ 7. certificates (optional)
# Adding one runs the flow in app/handlers/certificates.py and comes back here.


@router.callback_query(Registration.certs, CertCb.filter(F.action == "rdel"))
async def on_cert_remove(cb: CallbackQuery, callback_data: CertCb, state: FSMContext, session: AsyncSession, _: Translator, prefs: Prefs, bot: Bot) -> None:
    await cb.answer()
    items = list((await state.get_data()).get("reg_certs") or [])
    if callback_data.value.isdigit() and int(callback_data.value) < len(items):
        items.pop(int(callback_data.value))
        await state.update_data(reg_certs=items)
    await ask("certs", cb.message.chat.id, state, session, _, prefs, bot)


@router.callback_query(Registration.certs, RegCb.filter(F.action == "certs_done"))
async def on_certs_done(cb: CallbackQuery, state: FSMContext, session: AsyncSession, _: Translator, prefs: Prefs, bot: Bot) -> None:
    await cb.answer()
    await state.update_data(certs_done=True)
    await advance("certs", cb.message.chat.id, state, session, _, prefs, bot)


# ------------------------------------------------------------------ review & submit


@router.callback_query(Registration.review, RegCb.filter(F.action == "edit"))
async def on_edit(cb: CallbackQuery, _: Translator) -> None:
    await cb.answer()
    await cb.message.edit_reply_markup(reply_markup=kb.edit_fields_kb(_))


@router.callback_query(Registration.review, RegCb.filter(F.action == "back"))
async def on_edit_back(cb: CallbackQuery, _: Translator) -> None:
    await cb.answer()
    await cb.message.edit_reply_markup(reply_markup=kb.review_kb(_))


@router.callback_query(Registration.review, RegCb.filter(F.action == "submit"))
async def on_submit(
    cb: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    access: Access,
    _: Translator,
    prefs: Prefs,
    bot: Bot,
) -> None:
    if not prefs.registration_open:
        await cb.answer(_("reg.closed"), show_alert=True)
        return
    data = await state.get_data()
    missing = next((f for f in ORDER if not data.get(REQUIRED[f])), None)
    group = await session.get(Group, data["group_id"]) if data.get("group_id") else None
    if group is None or not group.is_active:
        missing = missing or "group"
    if await repo.get_student_by_tg(session, user.id):  # already submitted (e.g. a second review screen)
        await cb.answer()
        await drop_screen(bot, cb.message.chat.id, state)
        await state.clear()
        await tell_locked(cb.message, session, user, access, _)
        return
    await cb.answer()
    if missing:
        await ask(missing, cb.message.chat.id, state, session, _, prefs, bot)
        return

    doc = data["doc"]
    form = StudentForm(
        last_name=doc["last_name"],
        first_name=doc["first_name"],
        middle_name=data.get("middle_name"),
        birth_date=date.fromisoformat(doc["birth_date"]),
        gender=Gender(doc["gender"]),
        phone=data["phone"],
        group_id=group.id,
        doc_type=DocType(doc["doc_type"]),
        doc_number=doc["doc_number"],
        doc_expiry=date.fromisoformat(doc["doc_expiry"]) if doc.get("doc_expiry") else None,
        pinfl=doc.get("pinfl"),
        nationality=doc.get("nationality"),
        documents={kind: data[f"{kind.value}_files"] for kind in DocumentKind if data.get(f"{kind.value}_files")},
    )
    result = await repo.save_student(session, user.id, form)
    await repo.audit(
        session, repo.tg_actor(user.id), "student.register",
        entity="student", entity_id=result.student.id, summary=f"{result.student.full_name} · {group.name}",
        details=corrections(data),
    )
    for item in (data.get("reg_certs") or [])[: certs.MAX_PER_STUDENT]:
        cert = await repo.add_certificate(session, result.student, CertType(item["type"]), item.get("result") or "", item["files"])
        await repo.audit(
            session, repo.tg_actor(user.id), "certificate.submit", entity="student", entity_id=result.student.id,
            summary=f"{certs.label('en', cert)} · {result.student.full_name}",
        )
    await session.commit()
    await drop_screen(bot, cb.message.chat.id, state)
    await state.clear()
    log.info("Student %s registered (group %s)", user.id, group.name)

    await show_main_menu(cb.message, session, user, access, _, text=_("reg.done"))
    if prefs.notify_leaders:
        await _notify_leaders(bot, session, user.id, group, result.student.full_name)


async def _notify_leaders(bot: Bot, session: AsyncSession, student_tg: int, group: Group, name: str) -> None:
    for tg_id in await repo.leader_telegram_ids(session, group.id):
        if tg_id == student_tg:
            continue
        lu = await session.get(User, tg_id)
        try:
            await bot.send_message(tg_id, t(lu.language if lu else None, "notify.new_student", group=escape(group.name), name=escape(name)))
        except Exception as e:  # blocked the bot, etc.
            log.debug("Could not notify leader %s: %s", tg_id, e)


@router.message(Registration.check)
@router.message(Registration.certs)
@router.message(Registration.review)
async def on_use_buttons(message: Message, state: FSMContext, _: Translator, bot: Bot) -> None:
    await say_error(message, state, _("err.use_buttons"), bot)


# ------------------------------------------------------------------ registered students: missing documents


def missing_documents(student: Student) -> list[DocumentKind]:
    """Documents a registered student hasn't sent (e.g. added to the form after they registered).
    Documents already sent stay locked: only staff can replace them."""
    return [kind for kind in PAGED if student.document(kind) is None]


@router.callback_query(DocCb.filter(F.action == "add"))
async def on_add_document(
    cb: CallbackQuery, callback_data: DocCb, state: FSMContext, session: AsyncSession, user: User, _: Translator, prefs: Prefs, bot: Bot
) -> None:
    student = await repo.get_student_by_tg(session, user.id)
    kind = next((k for k in PAGED if k.value == callback_data.kind), None)
    if student is None or kind is None:
        await cb.answer()
        return
    if student.document(kind) is not None:
        await cb.answer(_("mydocs.already_sent"), show_alert=True)
        return
    await cb.answer()
    await drop_screen(bot, cb.message.chat.id, state)
    await state.set_data({"doc_kind": kind.value, "pages": [], "pages_msg": None})
    await state.set_state(MyDocuments.files)
    body = f"<b>{_(f'step.{kind.value}')}</b>\n\n{_(f'reg.{kind.value}', max=prefs.max_document_pages)}"
    await screen(bot, cb.message.chat.id, state, body, kb.cancel_kb(_))


@router.message(MyDocuments.files, F.photo | F.document)
async def on_my_document_file(message: Message, state: FSMContext, session: AsyncSession, user: User, _: Translator, prefs: Prefs, bot: Bot) -> None:
    kind = DocumentKind((await state.get_data())["doc_kind"])
    try:
        file = extract_file(message, kind)
    except FileRejected as e:
        await say_error(message, state, _(file_error(e, kind)), bot)
        return
    async with _locks[user.id]:
        if await state.get_state() != MyDocuments.files.state:
            return
        if files := await collect_page(message, state, file, _, prefs, bot):
            await _save_my_document(message.chat.id, kind, files, state, session, user, _, bot)


@router.callback_query(MyDocuments.files, RegCb.filter(F.action == "done"))
async def on_my_document_done(cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, _: Translator, bot: Bot) -> None:
    async with _locks[user.id]:
        data = await state.get_data()
        if not data.get("pages"):
            await cb.answer(_("err.no_pages"), show_alert=True)
            return
        await cb.answer()
        await delete_quietly(bot, cb.message.chat.id, cb.message.message_id)
        await _save_my_document(cb.message.chat.id, DocumentKind(data["doc_kind"]), data["pages"], state, session, user, _, bot)


@router.message(MyDocuments.files)
async def on_my_document_other(message: Message, state: FSMContext, _: Translator, bot: Bot) -> None:
    await say_error(message, state, _("file_err.expected"), bot)


async def _save_my_document(
    chat_id: int, kind: DocumentKind, files: list[dict], state: FSMContext, session: AsyncSession, user: User, _: Translator, bot: Bot
) -> None:
    await clear_error(chat_id, state, bot)
    await drop_screen(bot, chat_id, state)
    await state.clear()
    student = await repo.get_student_by_tg(session, user.id)
    if student is None or student.document(kind) is not None:  # e.g. sent twice at once
        return
    repo.set_document_files(student, kind, files)
    student.updated_at = repo.utcnow()
    await repo.audit(
        session, repo.tg_actor(user.id), "document.add", entity="student", entity_id=student.id,
        summary=f"{kind.value} · {student.full_name}", details={"files": len(files)},
    )
    await session.commit()
    log.info("Student %s sent a missing document (%s)", user.id, kind.value)
    text = _("mydocs.saved", doc=_(f"field.{kind.value}"))
    missing = missing_documents(student)
    if missing:
        text += "\n\n" + _("mydocs.missing")
    await bot.send_message(chat_id, text, reply_markup=kb.add_documents_kb(_, missing) if missing else None)
