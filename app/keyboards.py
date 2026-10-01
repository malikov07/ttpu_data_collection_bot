from __future__ import annotations

import math
import re
from typing import Callable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.callbacks import AdminCb, CertCb, CertReviewCb, EditFieldCb, GroupPickCb, LangCb, RegCb, StaffCb
from app.db.models import Account, Certificate, CertStatus, CertType, Group, Language, StaffRole, Student
from app.db.repo import Access, GroupStat
from app.i18n import Translator, t
from app.services import certificates as certs

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


# ------------------------------------------------------------------ group picker

# Up to this many groups fit on one screen; more are split by program first
# (IT, SE, CYB…), like the university's timetable.
FLAT_LIMIT = 12


def program_of(group_name: str) -> str:
    """"IT1-26" -> "IT", "MSc_MBA-26" -> "MSc"."""
    m = re.match(r"[A-Za-z]+", group_name)
    return m.group(0) if m else group_name


def group_sort_key(group_name: str) -> tuple:
    """Newest intake first: IT1-26, IT2-26, …, IT1-25 (the year follows the first dash)."""
    m = re.search(r"-(\d+)", group_name)
    return (-int(m.group(1)) if m else 0, group_name.upper())


def group_picker(
    _: Translator,
    groups: list[Group],
    program: str,
    *,
    pick: Callable[[Group], str],
    open_program: Callable[[str], str],
    label: Callable[[Group], str] = lambda g: g.name,
    columns: int = 3,
) -> list[list[InlineKeyboardButton]]:
    """Rows for choosing a group: programs first when there are many groups.

    ``program`` is the open program ("" = the programs screen); ``open_program``
    makes the callback data for a program button ("" goes back to programs).
    """
    programs = sorted({program_of(g.name) for g in groups}, key=str.upper)

    def chunk(buttons: list[InlineKeyboardButton], n: int) -> list[list[InlineKeyboardButton]]:
        return [buttons[i : i + n] for i in range(0, len(buttons), n)]

    def group_rows(items: list[Group]) -> list[list[InlineKeyboardButton]]:
        items = sorted(items, key=lambda g: group_sort_key(g.name))
        return chunk([_btn(label(g), pick(g)) for g in items], columns)

    if len(groups) <= FLAT_LIMIT or len(programs) == 1:
        return group_rows(groups)
    if program not in programs:
        return chunk([_btn(p, open_program(p)) for p in programs], 4)
    rows = group_rows([g for g in groups if program_of(g.name) == program])
    return [*rows, [_btn(_("btn.programs"), open_program(""))]]


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
        row = [KeyboardButton(text=_("btn.review_certs")), KeyboardButton(text=_("btn.export"))]
        if access.is_admin:
            row.append(KeyboardButton(text=_("btn.admin")))
        b.row(*row)
    if not access.sees_all:  # students, and group leaders (who are usually students too)
        if is_registered:
            b.row(KeyboardButton(text=_("btn.profile")), KeyboardButton(text=_("btn.certificates")))
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


def group_pick_kb(_: Translator, groups: list[Group], program: str = "") -> InlineKeyboardMarkup:
    return inline(
        *group_picker(
            _,
            groups,
            program,
            pick=lambda g: GroupPickCb(action="pick", group_id=g.id).pack(),
            open_program=lambda p: GroupPickCb(action="prog", program=p).pack(),
        )
    )


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
        [_btn(_("field.document"), EditFieldCb(field="document").pack()), _btn(_("field.certs"), EditFieldCb(field="certs").pack())],
        [_btn(_("btn.back"), RegCb(action="back").pack())],
    )


# ------------------------------------------------------------------ certificates

STATUS_ICON = {CertStatus.PENDING: "⏳", CertStatus.APPROVED: "✅", CertStatus.REJECTED: "❌"}


def my_certificates_kb(_: Translator, items: list[Certificate]) -> InlineKeyboardMarkup:
    """Add a certificate; remove one that isn't accepted (yet)."""
    rows = [[_btn(_("btn.add_certificate"), CertCb(action="add").pack())]] if len(items) < certs.MAX_PER_STUDENT else []
    for i, c in enumerate(items, start=1):
        if c.status != CertStatus.APPROVED:
            rows.append([_btn(f"🗑 {i}. {certs.label(_.lang, c)}"[:60], CertCb(action="del", id=c.id).pack())])
    return inline(*rows)


def cert_exit(_: Translator, back: bool) -> InlineKeyboardButton:
    """Leave adding a certificate: back to the registration step, or cancel."""
    return _btn(_("btn.back"), CertCb(action="back").pack()) if back else _btn(_("btn.cancel"), "cancel")


def cert_type_kb(_: Translator, *, back: bool = False) -> InlineKeyboardMarkup:
    rows = [[_btn(_(f"cert.type.{ct.value}"), CertCb(action="type", value=ct.value).pack()) for ct in group] for group in (
        (CertType.IELTS, CertType.TOEFL, CertType.SAT), (CertType.DUOLINGO, CertType.CEFR),
        (CertType.NATIONAL,), (CertType.OLYMPIAD, CertType.OTHER),
    )]
    return inline(*rows, [cert_exit(_, back)])


def cefr_kb(_: Translator, *, back: bool = False) -> InlineKeyboardMarkup:
    levels = [_btn(level, CertCb(action="result", value=level).pack()) for level in certs.CEFR_LEVELS]
    return inline(levels[:3], levels[3:], [cert_exit(_, back)])


def cert_exit_kb(_: Translator, *, back: bool = False) -> InlineKeyboardMarkup:
    return inline([cert_exit(_, back)])


def cert_pages_kb(_: Translator, *, back: bool = False) -> InlineKeyboardMarkup:
    return inline([_btn(_("btn.done"), CertCb(action="done").pack())], [cert_exit(_, back)])


def cert_confirm_kb(_: Translator, *, back: bool = False) -> InlineKeyboardMarkup:
    label = _("btn.cert_add_it") if back else _("btn.submit")
    return inline([_btn(label, CertCb(action="submit").pack())], [cert_exit(_, back)])


def reg_certs_kb(_: Translator, items: list[dict]) -> InlineKeyboardMarkup:
    """Registration step: add certificates (optional), remove one, then continue."""
    rows = [[_btn(_("btn.add_certificate"), CertCb(action="add").pack())]] if len(items) < certs.MAX_PER_STUDENT else []
    for i, c in enumerate(items):
        rows.append([_btn(f"🗑 {certs.describe(_.lang, c['type'], c['result'])}"[:60], CertCb(action="rdel", value=str(i)).pack())])
    rows.append([_btn(_("btn.continue") if items else _("btn.no_certs"), RegCb(action="certs_done").pack())])
    return inline(*rows)


def cert_line(_: Translator, c: Certificate, *, student: bool = False) -> str:
    text = f"{STATUS_ICON[c.status]} {certs.label(_.lang, c)}"
    if student:
        text += f" · {c.student.full_name} · {c.student.group.name}"
    return text[:64]


def cert_list_kb(_: Translator, items: list[Certificate], *, student: bool) -> InlineKeyboardMarkup:
    """Staff: one button per certificate (``student`` adds the student's name and group)."""
    rows = [[_btn(cert_line(_, c, student=student), CertReviewCb(action="open", id=c.id).pack())] for c in items]
    return inline(*rows, [_btn(_("btn.close"), StaffCb(action="close").pack())])


def cert_review_kb(_: Translator, cert: Certificate, *, can_review: bool) -> InlineKeyboardMarkup:
    decide = []
    if can_review and cert.status != CertStatus.APPROVED:
        decide.append(_btn(_("btn.cert_approve"), CertReviewCb(action="ok", id=cert.id).pack()))
    if can_review and cert.status != CertStatus.REJECTED:
        decide.append(_btn(_("btn.cert_reject"), CertReviewCb(action="no", id=cert.id).pack()))
    return inline(decide, [_btn(_("btn.close"), StaffCb(action="close").pack())])


# ------------------------------------------------------------------ staff


def staff_groups_kb(_: Translator, stats: list[GroupStat], program: str = "") -> InlineKeyboardMarkup:
    counts = {st.group.id: st.students for st in stats}
    return inline(
        *group_picker(
            _,
            [st.group for st in stats],
            program,
            pick=lambda g: StaffCb(action="group", group_id=g.id).pack(),
            open_program=lambda p: StaffCb(action="groups", value=p).pack(),
            label=lambda g: f"{g.name} · {counts[g.id]}",
            columns=2,
        )
    )


def staff_group_kb(
    _: Translator, group: Group, students: list[Student], *, page: int, total: int, offset: int, show_back: bool
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i, s in enumerate(students, start=offset + 1):
        b.row(_btn(f"{i}. {s.full_name}", StaffCb(action="card", student_id=s.id, group_id=group.id, page=page).pack()))
    if nav := _nav(_, page, pages(total, STUDENTS_PER_PAGE), lambda p: StaffCb(action="group", group_id=group.id, page=p).pack()):
        b.row(*nav)
    if show_back:
        b.row(_btn(_("btn.back"), StaffCb(action="groups", value=program_of(group.name)).pack()))
    return b.as_markup()


def student_card_kb(_: Translator, student: Student, *, can_edit: bool, can_delete: bool) -> InlineKeyboardMarkup:
    kinds = {d.kind.value for d in student.documents}
    docs = []
    if "passport" in kinds:
        docs.append(_btn(_("btn.passport"), StaffCb(action="doc", student_id=student.id, value="passport").pack()))
    if "cv" in kinds:
        docs.append(_btn(_("btn.cv"), StaffCb(action="doc", student_id=student.id, value="cv").pack()))
    certificates = []
    if student.certificates:
        label = _("btn.student_certs", n=len(student.certificates))
        certificates.append(_btn(label, CertReviewCb(action="student", id=student.id).pack()))
    actions = []
    if can_edit:
        actions.append(_btn(_("btn.edit_student"), StaffCb(action="edit", student_id=student.id).pack()))
    if can_delete:
        actions.append(_btn(_("btn.delete"), StaffCb(action="del", student_id=student.id).pack()))
    return inline(docs, certificates, actions, [_btn(_("btn.close"), StaffCb(action="close").pack())])


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


def staff_group_pick_kb(_: Translator, groups: list[Group], student_id: int, program: str = "") -> InlineKeyboardMarkup:
    rows = group_picker(
        _,
        groups,
        program,
        pick=lambda g: StaffCb(action="egroup", student_id=student_id, group_id=g.id).pack(),
        open_program=lambda p: StaffCb(action="egprog", student_id=student_id, value=p).pack(),
    )
    return inline(*rows, [_btn(_("btn.cancel"), "cancel")])


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


def admin_groups_kb(_: Translator, groups: list[Group], program: str = "", *, edupage: bool = True) -> InlineKeyboardMarkup:
    rows = group_picker(
        _,
        groups,
        program,
        pick=lambda g: AdminCb(action="group", id=g.id).pack(),
        open_program=lambda p: AdminCb(action="groups", value=p).pack(),
        label=lambda g: g.name if g.is_active else f"🙈 {g.name}",
    )
    rows.append([_btn(_("btn.add_groups"), AdminCb(action="add_groups").pack())])
    if edupage:
        rows.append([_btn(_("btn.edupage_import"), AdminCb(action="edupage").pack())])
    rows.append([_btn(_("btn.back"), AdminCb(action="panel").pack())])
    return inline(*rows)


def admin_group_kb(_: Translator, group: Group) -> InlineKeyboardMarkup:
    return inline(
        [
            _btn(_("btn.rename"), AdminCb(action="rename", id=group.id).pack()),
            _btn(_("btn.hide") if group.is_active else _("btn.show"), AdminCb(action="toggle", id=group.id).pack()),
        ],
        [_btn(_("btn.delete"), AdminCb(action="gdel", id=group.id).pack())],
        [_btn(_("btn.back"), AdminCb(action="groups", value=program_of(group.name)).pack())],
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


def admin_group_pick_kb(_: Translator, groups: list[Group], program: str = "") -> InlineKeyboardMarkup:
    rows = group_picker(
        _,
        groups,
        program,
        pick=lambda g: AdminCb(action="agroup", id=g.id).pack(),
        open_program=lambda p: AdminCb(action="agroup_prog", value=p).pack(),
    )
    return inline(*rows, [_btn(_("btn.cancel"), "cancel")])


def admin_settings_kb(_: Translator, *, registration_open: bool, notify_leaders: bool) -> InlineKeyboardMarkup:
    mark = lambda on: "✅" if on else "⬜️"  # noqa: E731
    return inline(
        [_btn(_("btn.toggle_registration", mark=mark(registration_open)), AdminCb(action="set", value="registration_open").pack())],
        [_btn(_("btn.toggle_notify", mark=mark(notify_leaders)), AdminCb(action="set", value="notify_leaders").pack())],
        [_btn(_("btn.back"), AdminCb(action="panel").pack())],
    )


def skip_kb(_: Translator, data: str) -> InlineKeyboardMarkup:
    return inline([_btn(_("btn.skip"), data)], [_btn(_("btn.cancel"), "cancel")])
