from __future__ import annotations

import math
from typing import Callable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.callbacks import AdminCb, EditFieldCb, GroupPickCb, LangCb, RegCb, StaffCb
from app.db.models import Account, Group, Language, StaffRole, Student
from app.db.repo import Access, GroupStat
from app.i18n import Translator, t

GROUPS_PER_PAGE = 24
STUDENTS_PER_PAGE = 10


def pages(total: int, per_page: int) -> int:
    return max(1, math.ceil(total / per_page))


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _nav(_: Translator, page: int, total_pages: int, make: Callable[[int], str]) -> list[InlineKeyboardButton]:
    if total_pages <= 1:
        return []
    row = [_btn(_("btn.prev") if page > 0 else " ", make(page - 1) if page > 0 else "noop")]
    row.append(_btn(f"{page + 1} / {total_pages}", "noop"))
    row.append(_btn(_("btn.next") if page < total_pages - 1 else " ", make(page + 1) if page < total_pages - 1 else "noop"))
    return row


def inline(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[r for r in rows if r])


# ------------------------------------------------------------------ menus


def language_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for lang in (Language.UZ, Language.RU, Language.EN):
        b.button(text=t(lang, "lang.name"), callback_data=LangCb(code=lang.value))
    b.adjust(1)
    return b.as_markup()


def main_menu(_: Translator, access: Access, *, is_registered: bool) -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    if access.is_staff:
        b.row(KeyboardButton(text=_("btn.students")), KeyboardButton(text=_("btn.search")))
        row = [KeyboardButton(text=_("btn.export"))]
        if access.is_admin:
            row.append(KeyboardButton(text=_("btn.admin")))
        b.row(*row)
    if not access.sees_all:  # students, and group leaders (who are usually students too)
        if is_registered:
            b.row(KeyboardButton(text=_("btn.profile")))
        else:
            b.row(KeyboardButton(text=_("btn.register")))
    b.row(KeyboardButton(text=_("btn.language")), KeyboardButton(text=_("btn.help")))
    return b.as_markup(resize_keyboard=True, is_persistent=True)


def cancel_kb(_: Translator) -> InlineKeyboardMarkup:
    return inline([_btn(_("btn.cancel"), "cancel")])


# ------------------------------------------------------------------ registration


def consent_kb(_: Translator) -> InlineKeyboardMarkup:
    return inline([_btn(_("btn.consent"), RegCb(action="consent").pack())])


NAME_FIELDS = ("last_name", "first_name", "middle_name")


def _field_btn(_: Translator, field: str) -> InlineKeyboardButton:
    return _btn(f"✏️ {_(f'sfield.{field}')}", EditFieldCb(field=field).pack())


def check_kb(_: Translator) -> InlineKeyboardMarkup:
    """Confirm what was read, or fix one field at a time."""
    return inline(
        [_btn(_("btn.correct"), RegCb(action="correct").pack())],
        [_field_btn(_, "last_name"), _field_btn(_, "first_name")],
        [_field_btn(_, "middle_name"), _field_btn(_, "gender")],
        [_btn(_("btn.retake"), RegCb(action="retake").pack())],
    )


def reg_gender_kb(_: Translator) -> InlineKeyboardMarkup:
    return inline(
        [
            _btn(_("gender.male"), EditFieldCb(field="gender", value="male").pack()),
            _btn(_("gender.female"), EditFieldCb(field="gender", value="female").pack()),
        ],
        [_btn(_("btn.back"), RegCb(action="return").pack())],
    )


def back_kb(_: Translator) -> InlineKeyboardMarkup:
    return inline([_btn(_("btn.back"), RegCb(action="return").pack())])


def phone_kb(_: Translator) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=_("btn.share_phone"), request_contact=True)], [KeyboardButton(text=_("btn.cancel"))]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def group_pick_kb(_: Translator, groups: list[Group], page: int = 0, *, extra: list[InlineKeyboardButton] | None = None) -> InlineKeyboardMarkup:
    total = pages(len(groups), GROUPS_PER_PAGE)
    page = min(max(page, 0), total - 1)
    b = InlineKeyboardBuilder()
    for g in groups[page * GROUPS_PER_PAGE : (page + 1) * GROUPS_PER_PAGE]:
        b.button(text=g.name, callback_data=GroupPickCb(action="pick", group_id=g.id))
    b.adjust(3)
    if nav := _nav(_, page, total, lambda p: GroupPickCb(action="page", page=p).pack()):
        b.row(*nav)
    if extra:
        b.row(*extra)
    return b.as_markup()


def pages_kb(_: Translator) -> InlineKeyboardMarkup:
    return inline([_btn(_("btn.done"), RegCb(action="done").pack())])


def review_kb(_: Translator) -> InlineKeyboardMarkup:
    return inline(
        [_btn(_("btn.submit"), RegCb(action="submit").pack())],
        [_btn(_("btn.edit"), RegCb(action="edit").pack())],
    )


def edit_fields_kb(_: Translator) -> InlineKeyboardMarkup:
    return inline(
        [_field_btn(_, "last_name"), _field_btn(_, "first_name")],
        [_field_btn(_, "middle_name"), _field_btn(_, "gender")],
        [_btn(_("field.phone"), EditFieldCb(field="phone").pack()), _btn(_("field.group"), EditFieldCb(field="group").pack())],
        [_btn(_("field.photo"), EditFieldCb(field="photo").pack()), _btn(_("field.cv"), EditFieldCb(field="cv").pack())],
        [_btn(_("field.document"), EditFieldCb(field="document").pack())],
        [_btn(_("btn.back"), RegCb(action="back").pack())],
    )


# ------------------------------------------------------------------ staff


def staff_groups_kb(_: Translator, stats: list[GroupStat], page: int = 0) -> InlineKeyboardMarkup:
    total = pages(len(stats), GROUPS_PER_PAGE)
    page = min(max(page, 0), total - 1)
    b = InlineKeyboardBuilder()
    for st in stats[page * GROUPS_PER_PAGE : (page + 1) * GROUPS_PER_PAGE]:
        b.button(text=f"{st.group.name}  ·  {st.students}", callback_data=StaffCb(action="group", group_id=st.group.id))
    b.adjust(2)
    if nav := _nav(_, page, total, lambda p: StaffCb(action="groups", page=p).pack()):
        b.row(*nav)
    return b.as_markup()


def staff_group_kb(
    _: Translator, group: Group, students: list[Student], *, page: int, total: int, offset: int, show_back: bool
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i, s in enumerate(students, start=offset + 1):
        b.row(_btn(f"{i}. {s.full_name}", StaffCb(action="card", student_id=s.id, group_id=group.id, page=page).pack()))
    if nav := _nav(_, page, pages(total, STUDENTS_PER_PAGE), lambda p: StaffCb(action="group", group_id=group.id, page=p).pack()):
        b.row(*nav)
    if show_back:
        b.row(_btn(_("btn.back"), StaffCb(action="groups").pack()))
    return b.as_markup()


def student_card_kb(_: Translator, student: Student, *, can_edit: bool, can_delete: bool) -> InlineKeyboardMarkup:
    kinds = {d.kind.value for d in student.documents}
    docs = []
    if "passport" in kinds:
        docs.append(_btn(_("btn.passport"), StaffCb(action="doc", student_id=student.id, value="passport").pack()))
    if "cv" in kinds:
        docs.append(_btn(_("btn.cv"), StaffCb(action="doc", student_id=student.id, value="cv").pack()))
    actions = []
    if can_edit:
        actions.append(_btn(_("btn.edit_student"), StaffCb(action="edit", student_id=student.id).pack()))
    if can_delete:
        actions.append(_btn(_("btn.delete"), StaffCb(action="del", student_id=student.id).pack()))
    return inline(docs, actions, [_btn(_("btn.close"), StaffCb(action="close").pack())])


EDITABLE = ("last_name", "first_name", "middle_name", "birth_date", "gender", "phone", "group")


def student_edit_kb(_: Translator, student: Student) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for f in EDITABLE:
        b.button(text=_(f"sfield.{f}"), callback_data=StaffCb(action="efield", student_id=student.id, value=f))
    b.button(text=_("btn.back"), callback_data=StaffCb(action="card", student_id=student.id, value="refresh"))
    b.adjust(2, 2, 2, 1, 1)
    return b.as_markup()


def gender_pick_kb(_: Translator, student_id: int) -> InlineKeyboardMarkup:
    return inline(
        [
            _btn(_("gender.male"), StaffCb(action="egender", student_id=student_id, value="male").pack()),
            _btn(_("gender.female"), StaffCb(action="egender", student_id=student_id, value="female").pack()),
        ],
        [_btn(_("btn.cancel"), "cancel")],
    )


def staff_group_pick_kb(_: Translator, groups: list[Group], student_id: int, page: int = 0) -> InlineKeyboardMarkup:
    total = pages(len(groups), GROUPS_PER_PAGE)
    page = min(max(page, 0), total - 1)
    b = InlineKeyboardBuilder()
    for g in groups[page * GROUPS_PER_PAGE : (page + 1) * GROUPS_PER_PAGE]:
        b.button(text=g.name, callback_data=StaffCb(action="egroup", student_id=student_id, group_id=g.id))
    b.adjust(3)
    if nav := _nav(_, page, total, lambda p: StaffCb(action="egpage", student_id=student_id, page=p).pack()):
        b.row(*nav)
    b.row(_btn(_("btn.cancel"), "cancel"))
    return b.as_markup()


def confirm_kb(_: Translator, yes: str, no: str) -> InlineKeyboardMarkup:
    return inline([_btn(_("btn.yes_delete"), yes), _btn(_("btn.no"), no)])


def search_results_kb(students: list[Student]) -> InlineKeyboardMarkup:
    return inline(
        *[
            [_btn(f"{s.full_name} · {s.group.name}", StaffCb(action="card", student_id=s.id, group_id=s.group_id).pack())]
            for s in students
        ]
    )


# ------------------------------------------------------------------ admin


def admin_panel_kb(_: Translator) -> InlineKeyboardMarkup:
    return inline(
        [_btn(_("btn.admin_groups"), AdminCb(action="groups").pack()), _btn(_("btn.admin_accounts"), AdminCb(action="accounts").pack())],
        [_btn(_("btn.admin_settings"), AdminCb(action="settings").pack())],
    )


def admin_groups_kb(_: Translator, groups: list[Group], page: int = 0) -> InlineKeyboardMarkup:
    total = pages(len(groups), GROUPS_PER_PAGE)
    page = min(max(page, 0), total - 1)
    b = InlineKeyboardBuilder()
    for g in groups[page * GROUPS_PER_PAGE : (page + 1) * GROUPS_PER_PAGE]:
        b.button(text=g.name if g.is_active else f"🙈 {g.name}", callback_data=AdminCb(action="group", id=g.id, page=page))
    b.adjust(3)
    if nav := _nav(_, page, total, lambda p: AdminCb(action="groups", page=p).pack()):
        b.row(*nav)
    b.row(_btn(_("btn.add_groups"), AdminCb(action="add_groups").pack()))
    b.row(_btn(_("btn.back"), AdminCb(action="panel").pack()))
    return b.as_markup()


def admin_group_kb(_: Translator, group: Group, page: int) -> InlineKeyboardMarkup:
    return inline(
        [
            _btn(_("btn.rename"), AdminCb(action="rename", id=group.id, page=page).pack()),
            _btn(_("btn.hide") if group.is_active else _("btn.show"), AdminCb(action="toggle", id=group.id, page=page).pack()),
        ],
        [_btn(_("btn.delete"), AdminCb(action="gdel", id=group.id, page=page).pack())],
        [_btn(_("btn.back"), AdminCb(action="groups", page=page).pack())],
    )


ROLE_ICON = {StaffRole.ADMIN: "🛡", StaffRole.TUTOR: "🎓", StaffRole.LEADER: "👥"}


def admin_accounts_kb(_: Translator, accounts: list[Account]) -> InlineKeyboardMarkup:
    rows = []
    for a in accounts:
        icons = "".join(dict.fromkeys(ROLE_ICON[r.role] for r in a.roles)) or "·"
        paused = "" if a.is_active else " ⏸"
        rows.append([_btn(f"{icons} {a.label} ({a.username}){paused}", AdminCb(action="account", id=a.id).pack())])
    rows.append([_btn(_("btn.new_account"), AdminCb(action="new").pack())])
    rows.append([_btn(_("btn.back"), AdminCb(action="panel").pack())])
    return inline(*rows)


def admin_account_kb(_: Translator, account: Account) -> InlineKeyboardMarkup:
    return inline(
        [
            _btn(_("btn.reset_password"), AdminCb(action="reset", id=account.id).pack()),
            _btn(_("btn.disable") if account.is_active else _("btn.enable"), AdminCb(action="active", id=account.id).pack()),
        ],
        [_btn(_("btn.delete"), AdminCb(action="adel", id=account.id).pack())],
        [_btn(_("btn.back"), AdminCb(action="accounts").pack())],
    )


def role_pick_kb(_: Translator) -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"{ROLE_ICON[r]} {role_title(_, r)}", AdminCb(action="role", value=r.value).pack())]
        for r in (StaffRole.LEADER, StaffRole.TUTOR, StaffRole.ADMIN)
    ]
    return inline(*rows, [_btn(_("btn.cancel"), "cancel")])


def role_title(_: Translator, role: StaffRole) -> str:
    """Short role name without the emoji/groups decoration."""
    text = _(f"role.{role.value}", groups="").split(" ", 1)[-1]
    return text.split(":")[0].strip()


def admin_group_pick_kb(_: Translator, groups: list[Group], page: int = 0) -> InlineKeyboardMarkup:
    total = pages(len(groups), GROUPS_PER_PAGE)
    page = min(max(page, 0), total - 1)
    b = InlineKeyboardBuilder()
    for g in groups[page * GROUPS_PER_PAGE : (page + 1) * GROUPS_PER_PAGE]:
        b.button(text=g.name, callback_data=AdminCb(action="agroup", id=g.id))
    b.adjust(3)
    if nav := _nav(_, page, total, lambda p: AdminCb(action="agroup_page", page=p).pack()):
        b.row(*nav)
    b.row(_btn(_("btn.cancel"), "cancel"))
    return b.as_markup()


def admin_settings_kb(_: Translator, *, registration_open: bool, notify_leaders: bool) -> InlineKeyboardMarkup:
    mark = lambda on: "✅" if on else "⬜️"  # noqa: E731
    return inline(
        [_btn(_("btn.toggle_registration", mark=mark(registration_open)), AdminCb(action="set", value="registration_open").pack())],
        [_btn(_("btn.toggle_notify", mark=mark(notify_leaders)), AdminCb(action="set", value="notify_leaders").pack())],
        [_btn(_("btn.back"), AdminCb(action="panel").pack())],
    )


def skip_kb(_: Translator, data: str) -> InlineKeyboardMarkup:
    return inline([_btn(_("btn.skip"), data)], [_btn(_("btn.cancel"), "cancel")])
