"""Staff in the bot: browse, view documents, edit, delete (admins), search, export.

Tutors and admins see all groups; leaders see and edit their own group(s).
"""

from __future__ import annotations

import contextlib
import logging
from datetime import date
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardMarkup,
    InputMediaDocument,
    InputMediaPhoto,
    Message,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import keyboards as kb
from app.callbacks import StaffCb
from app.config import Settings
from app.db import repo
from app.db.models import DocumentKind, Gender, Group, Student, User
from app.db.repo import Access
from app.i18n import Translator, menu_buttons, variants
from app.services.documents import read_upload
from app.services.export import students_xlsx
from app.services.prefs import Prefs
from app.services.validators import (
    ValidationError,
    normalize_name_part,
    normalize_phone,
    parse_birth_date,
)
from app.states import StaffStates
from app.views import fmt_date, render_staff_card

log = logging.getLogger(__name__)
router = Router(name="staff")


def is_staff(_event: object, access: Access) -> bool:
    return access.is_staff


router.message.filter(is_staff)
router.callback_query.filter(is_staff)


# ------------------------------------------------------------------ lists


async def render_groups(session: AsyncSession, access: Access, _: Translator, program: str = "") -> tuple[str, InlineKeyboardMarkup | None]:
    stats = await repo.list_group_stats(session, access.visible_group_ids())
    if not stats:
        return _("staff.no_groups"), None
    return (
        _("staff.groups", students=sum(s.students for s in stats), groups=len(stats)),
        kb.staff_groups_kb(_, stats, program),
    )


async def render_group(session: AsyncSession, access: Access, _: Translator, group: Group, page: int) -> tuple[str, InlineKeyboardMarkup]:
    total = await repo.count_students(session, group.id)
    page = min(max(page, 0), kb.pages(total, kb.STUDENTS_PER_PAGE) - 1)
    students = await repo.list_students(session, group.id, offset=page * kb.STUDENTS_PER_PAGE, limit=kb.STUDENTS_PER_PAGE)
    show_back = access.sees_all or len(access.leader_group_ids) > 1
    text = _("staff.group", group=escape(group.name), n=total) if total else _("staff.group_empty", group=escape(group.name))
    markup = kb.staff_group_kb(
        _, group, students, page=page, total=total, offset=page * kb.STUDENTS_PER_PAGE, show_back=show_back
    )
    return text, markup


@router.message(Command("students"))
@router.message(F.text.in_(variants("btn.students")))
async def cmd_students(message: Message, state: FSMContext, session: AsyncSession, access: Access, _: Translator) -> None:
    await state.clear()
    visible = access.visible_group_ids()
    if visible is not None and len(visible) == 1 and (group := await session.get(Group, visible[0])):
        text, markup = await render_group(session, access, _, group, 0)
    else:
        text, markup = await render_groups(session, access, _)
    await message.answer(text, reply_markup=markup)


@router.callback_query(StaffCb.filter(F.action == "groups"))
async def on_groups(cb: CallbackQuery, callback_data: StaffCb, session: AsyncSession, access: Access, _: Translator) -> None:
    text, markup = await render_groups(session, access, _, callback_data.value)
    await cb.answer()
    await cb.message.edit_text(text, reply_markup=markup)


@router.callback_query(StaffCb.filter(F.action == "group"))
async def on_group(cb: CallbackQuery, callback_data: StaffCb, session: AsyncSession, access: Access, _: Translator) -> None:
    group = await session.get(Group, callback_data.group_id)
    if group is None or not access.can_view_group(group.id):
        await cb.answer(_("access_denied"), show_alert=True)
        return
    text, markup = await render_group(session, access, _, group, callback_data.page)
    await cb.answer()
    await cb.message.edit_text(text, reply_markup=markup)


# ------------------------------------------------------------------ student card


async def _visible_student(session: AsyncSession, access: Access, student_id: int) -> Student | None:
    student = await repo.get_student(session, student_id)
    if student is None or not access.can_view_group(student.group_id):
        return None
    return student


async def send_card(bot: Bot, chat_id: int, student: Student, access: Access, _: Translator, settings: Settings) -> None:
    """The card is a separate message (photo + caption when there is a 3x4 photo)."""
    text = render_staff_card(_, student, ZoneInfo(settings.timezone))
    markup = kb.student_card_kb(_, student, can_edit=access.can_edit_group(student.group_id), can_delete=access.is_admin)
    photo = student.document(DocumentKind.PHOTO)
    file = photo.files[0] if photo and photo.files else None
    try:
        if file and file["type"] == "photo":
            await bot.send_photo(chat_id, file["file_id"], caption=text, reply_markup=markup)
            return
        if file and file["type"] == "upload":
            data = read_upload(file, settings.uploads_dir)
            await bot.send_photo(chat_id, BufferedInputFile(data, "photo.jpg"), caption=text, reply_markup=markup)
            return
    except Exception as e:  # the photo is unavailable: fall back to text
        log.warning("Could not send photo of student %s: %s", student.id, e)
    await bot.send_message(chat_id, text, reply_markup=markup)


@router.callback_query(StaffCb.filter(F.action == "card"))
async def on_card(
    cb: CallbackQuery, callback_data: StaffCb, session: AsyncSession, access: Access, _: Translator, settings: Settings, bot: Bot
) -> None:
    student = await _visible_student(session, access, callback_data.student_id)
    if student is None:
        await cb.answer(_("staff.not_found"), show_alert=True)
        return
    await cb.answer()
    if callback_data.value == "refresh":  # "Back" from the edit menu
        with contextlib.suppress(Exception):
            await cb.message.edit_reply_markup(
                reply_markup=kb.student_card_kb(_, student, can_edit=access.can_edit_group(student.group_id), can_delete=access.is_admin)
            )
        return
    await send_card(bot, cb.message.chat.id, student, access, _, settings)


@router.callback_query(StaffCb.filter(F.action == "close"))
async def on_close(cb: CallbackQuery) -> None:
    await cb.answer()
    with contextlib.suppress(Exception):
        await cb.message.delete()


@router.callback_query(StaffCb.filter(F.action == "doc"))
async def on_document(
    cb: CallbackQuery, callback_data: StaffCb, session: AsyncSession, access: Access, _: Translator, settings: Settings, bot: Bot
) -> None:
    student = await _visible_student(session, access, callback_data.student_id)
    kind = DocumentKind(callback_data.value) if callback_data.value in {k.value for k in DocumentKind} else None
    doc = student.document(kind) if student and kind else None
    if doc is None:
        await cb.answer(_("staff.not_found"), show_alert=True)
        return
    await cb.answer()
    await repo.audit(
        session, repo.actor_of(access, cb.from_user.id), "document.view", entity="student", entity_id=student.id,
        summary=f"{kind.value} · {student.full_name}",
    )
    await session.commit()
    caption = f"{escape(student.full_name)} · {escape(student.group.name)}"
    await send_files(bot, cb.message.chat.id, doc.files, caption, settings.uploads_dir)


async def send_files(bot: Bot, chat_id: int, files: list[dict], caption: str, uploads_dir: Path) -> None:
    def media(f: dict):
        if f["type"] == "upload":
            return BufferedInputFile(read_upload(f, uploads_dir), filename=f.get("name") or "file")
        return f["file_id"]

    if len(files) == 1:
        f = files[0]
        send = bot.send_photo if f["type"] == "photo" else bot.send_document
        await send(chat_id, media(f), caption=caption)
        return
    if all(f["type"] == "photo" for f in files):
        await bot.send_media_group(
            chat_id, [InputMediaPhoto(media=f["file_id"], caption=caption if i == 0 else None) for i, f in enumerate(files[:10])]
        )
        return
    if all(f["type"] == "document" for f in files):
        await bot.send_media_group(
            chat_id, [InputMediaDocument(media=f["file_id"], caption=caption if i == 0 else None) for i, f in enumerate(files[:10])]
        )
        return
    for i, f in enumerate(files):
        send = bot.send_photo if f["type"] == "photo" else bot.send_document
        await send(chat_id, media(f), caption=caption if i == 0 else None)


# ------------------------------------------------------------------ edit


TEXT_FIELDS = {"last_name", "first_name", "middle_name", "birth_date", "phone"}


@router.callback_query(StaffCb.filter(F.action == "edit"))
async def on_edit(cb: CallbackQuery, callback_data: StaffCb, session: AsyncSession, access: Access, _: Translator) -> None:
    student = await _visible_student(session, access, callback_data.student_id)
    if student is None or not access.can_edit_group(student.group_id):
        await cb.answer(_("access_denied"), show_alert=True)
        return
    await cb.answer()
    await cb.message.edit_reply_markup(reply_markup=kb.student_edit_kb(_, student))


@router.callback_query(StaffCb.filter(F.action == "efield"))
async def on_edit_field(
    cb: CallbackQuery, callback_data: StaffCb, state: FSMContext, session: AsyncSession, access: Access, _: Translator
) -> None:
    student = await _visible_student(session, access, callback_data.student_id)
    field = callback_data.value
    if student is None or not access.can_edit_group(student.group_id) or field not in kb.EDITABLE:
        await cb.answer(_("access_denied"), show_alert=True)
        return
    await cb.answer()
    if field == "gender":
        await cb.message.answer(_("staff.edit_gender"), reply_markup=kb.gender_pick_kb(_, student.id))
        return
    if field == "group":
        groups = await repo.list_groups(session, ids=access.visible_group_ids())
        await cb.message.answer(_("staff.edit_group"), reply_markup=kb.staff_group_pick_kb(_, groups, student.id))
        return
    current = fmt_date(student.birth_date) if field == "birth_date" else (getattr(student, field) or "—")
    key = "staff.edit_date_prompt" if field == "birth_date" else "staff.edit_prompt"
    prompt = await cb.message.answer(
        _(key, field=_(f"sfield.{field}"), current=escape(str(current))), reply_markup=kb.cancel_kb(_)
    )
    await state.set_state(StaffStates.edit_value)
    await state.update_data(edit_student=student.id, edit_field=field, screen_id=prompt.message_id)


async def _save(
    session: AsyncSession, student: Student, changes: dict, access: Access, telegram_id: int
) -> None:
    diff = {}
    for field, value in changes.items():
        old = getattr(student, field)
        if old != value:
            diff[field] = [old.isoformat() if isinstance(old, date) else str(old) if old is not None else None,
                           value.isoformat() if isinstance(value, date) else str(value) if value is not None else None]
            setattr(student, field, value)
    if not diff:
        return
    if {"last_name", "first_name", "middle_name"} & diff.keys():
        student.set_names(student.last_name, student.first_name, student.middle_name)
    student.updated_at = repo.utcnow()
    await repo.audit(
        session, repo.actor_of(access, telegram_id), "student.edit", entity="student", entity_id=student.id,
        summary=student.full_name, details=diff,
    )
    await session.commit()


@router.message(StaffStates.edit_value, F.text, ~F.text.startswith("/"), ~F.text.in_(menu_buttons()))
async def on_edit_value(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    access: Access,
    _: Translator,
    prefs: Prefs,
    settings: Settings,
    bot: Bot,
) -> None:
    data = await state.get_data()
    student = await _visible_student(session, access, data.get("edit_student", 0))
    field = data.get("edit_field")
    if student is None or not access.can_edit_group(student.group_id):
        await state.clear()
        await message.answer(_("access_denied"))
        return
    try:
        if field == "birth_date":
            value = parse_birth_date(message.text, min_age=prefs.min_student_age, max_age=prefs.max_student_age)
        elif field == "phone":
            value = normalize_phone(message.text)
        elif field == "middle_name" and message.text.strip() in {"-", "—"}:
            value = None
        else:
            value = normalize_name_part(message.text)
    except ValidationError:
        await message.answer(_("staff.invalid_value"))
        return
    await _save(session, student, {field: value}, access, message.from_user.id)
    with contextlib.suppress(Exception):
        await bot.delete_message(message.chat.id, data.get("screen_id"))
    await state.clear()
    await message.answer(_("staff.saved"))
    await send_card(bot, message.chat.id, await repo.get_student(session, student.id), access, _, settings)


@router.callback_query(StaffCb.filter(F.action == "egender"))
async def on_edit_gender(
    cb: CallbackQuery, callback_data: StaffCb, session: AsyncSession, access: Access, _: Translator, settings: Settings, bot: Bot
) -> None:
    student = await _visible_student(session, access, callback_data.student_id)
    if student is None or not access.can_edit_group(student.group_id) or callback_data.value not in {"male", "female"}:
        await cb.answer(_("access_denied"), show_alert=True)
        return
    await _save(session, student, {"gender": Gender(callback_data.value)}, access, cb.from_user.id)
    await cb.answer(_("staff.saved"))
    with contextlib.suppress(Exception):
        await cb.message.delete()
    await send_card(bot, cb.message.chat.id, await repo.get_student(session, student.id), access, _, settings)


@router.callback_query(StaffCb.filter(F.action == "egprog"))
async def on_edit_group_program(cb: CallbackQuery, callback_data: StaffCb, session: AsyncSession, access: Access, _: Translator) -> None:
    groups = await repo.list_groups(session, ids=access.visible_group_ids())
    await cb.answer()
    await cb.message.edit_reply_markup(reply_markup=kb.staff_group_pick_kb(_, groups, callback_data.student_id, callback_data.value))


@router.callback_query(StaffCb.filter(F.action == "egroup"))
async def on_edit_group(
    cb: CallbackQuery, callback_data: StaffCb, session: AsyncSession, access: Access, _: Translator, settings: Settings, bot: Bot
) -> None:
    student = await _visible_student(session, access, callback_data.student_id)
    group = await session.get(Group, callback_data.group_id)
    if student is None or group is None or not access.can_edit_group(student.group_id) or not access.can_edit_group(group.id):
        await cb.answer(_("access_denied"), show_alert=True)
        return
    if group.id != student.group_id:
        old = student.group.name
        student.group_id = group.id
        student.updated_at = repo.utcnow()
        await repo.audit(
            session, repo.actor_of(access, cb.from_user.id), "student.edit", entity="student", entity_id=student.id,
            summary=student.full_name, details={"group": [old, group.name]},
        )
        await session.commit()
    await cb.answer(_("staff.saved"))
    with contextlib.suppress(Exception):
        await cb.message.delete()
    student_id = student.id  # read before expire_all(): expired attributes can't lazy-load here
    session.expire_all()
    await send_card(bot, cb.message.chat.id, await repo.get_student(session, student_id), access, _, settings)


# ------------------------------------------------------------------ delete (admins)


@router.callback_query(StaffCb.filter(F.action == "del"))
async def on_delete(cb: CallbackQuery, callback_data: StaffCb, session: AsyncSession, access: Access, _: Translator) -> None:
    student = await repo.get_student(session, callback_data.student_id) if access.is_admin else None
    if student is None:
        await cb.answer(_("access_denied"), show_alert=True)
        return
    await cb.answer()
    await cb.message.answer(
        _("staff.delete_confirm", name=escape(student.full_name), group=escape(student.group.name)),
        reply_markup=kb.confirm_kb(
            _, yes=StaffCb(action="del_ok", student_id=student.id).pack(), no=StaffCb(action="close").pack()
        ),
    )


@router.callback_query(StaffCb.filter(F.action == "del_ok"))
async def on_delete_ok(cb: CallbackQuery, callback_data: StaffCb, session: AsyncSession, access: Access, _: Translator) -> None:
    student = await repo.get_student(session, callback_data.student_id) if access.is_admin else None
    if student is None:
        await cb.answer(_("staff.not_found"), show_alert=True)
        return
    name, group = student.full_name, student.group.name
    await repo.delete_student(session, student)
    await repo.audit(
        session, repo.actor_of(access, cb.from_user.id), "student.delete", entity="student",
        entity_id=callback_data.student_id, summary=f"{name} · {group}",
    )
    await session.commit()
    await cb.answer()
    await cb.message.edit_text(_("staff.deleted", name=escape(name)))


# ------------------------------------------------------------------ search


@router.message(F.text.in_(variants("btn.search")))
async def cmd_search_button(message: Message, state: FSMContext, _: Translator) -> None:
    await state.set_state(StaffStates.search)
    await message.answer(_("staff.search_prompt"))


@router.message(Command("find"))
async def cmd_find(message: Message, command: CommandObject, state: FSMContext, session: AsyncSession, access: Access, _: Translator) -> None:
    if not command.args:
        await cmd_search_button(message, state, _)
        return
    await _search(message, command.args, session, access, _)


@router.message(StaffStates.search, F.text, ~F.text.startswith("/"), ~F.text.in_(menu_buttons()))
async def on_search_text(message: Message, state: FSMContext, session: AsyncSession, access: Access, _: Translator) -> None:
    if await _search(message, message.text, session, access, _):
        await state.clear()


async def _search(message: Message, query: str, session: AsyncSession, access: Access, _: Translator) -> bool:
    query = query.strip()
    if len(query.lstrip("@")) < 2:
        await message.answer(_("staff.search_short"))
        return False
    results = await repo.search_students(session, query, access.visible_group_ids())
    safe = escape(query[:50])
    if not results:
        await message.answer(_("staff.search_empty", query=safe))
    else:
        await message.answer(_("staff.search_results", query=safe, n=len(results)), reply_markup=kb.search_results_kb(results))
    return True


# ------------------------------------------------------------------ export


@router.message(Command("export"))
@router.message(F.text.in_(variants("btn.export")))
async def cmd_export(message: Message, session: AsyncSession, user: User, access: Access, _: Translator, bot: Bot) -> None:
    stmt = select(Student).options(*repo.student_options())
    if (visible := access.visible_group_ids()) is not None:
        stmt = stmt.where(Student.group_id.in_(visible))
    students = list((await session.scalars(stmt)).all())
    data = students_xlsx(students, (user.language or "uz"))
    today = date.today()
    await repo.audit(session, repo.actor_of(access, user.id), "students.export", summary=f"{len(students)} rows (bot)")
    await session.commit()
    await bot.send_document(
        message.chat.id,
        BufferedInputFile(data, filename=f"ttpu-students-{today.isoformat()}.xlsx"),
        caption=_("staff.export_caption", n=len(students), date=fmt_date(today)),
    )
