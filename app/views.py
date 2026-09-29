"""Rendering of bot texts (HTML parse mode)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from html import escape
from zoneinfo import ZoneInfo

from app.db.models import Account, DocType, DocumentKind, Gender, StaffRole, Student
from app.db.repo import Access
from app.i18n import Translator
from app.services.validators import age_on, format_phone


def fmt_date(d: date | str | None) -> str:
    if d is None:
        return "—"
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return d.strftime("%d.%m.%Y")


def fmt_dt(dt: datetime, tz: ZoneInfo) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).strftime("%d.%m.%Y %H:%M")


def gender_label(_: Translator, gender: Gender | str) -> str:
    return _(f"gender.{Gender(gender).value}")


def document_line(_: Translator, doc_type: str | None, number: str | None, expiry: date | str | None) -> str:
    if not number:
        return "—"
    kind = _(f"doctype.{DocType(doc_type).value}") if doc_type else ""
    return f"{kind} <code>{escape(number)}</code> · {fmt_date(expiry)}".strip()


def docs_line(_: Translator, *, passport: bool, photo: bool, cv: bool) -> str:
    mark = lambda ok: _("doc.ok") if ok else _("doc.missing")  # noqa: E731
    return _("docs.line", passport=mark(passport), photo=mark(photo), cv=mark(cv))


def student_docs_line(_: Translator, s: Student) -> str:
    return docs_line(
        _,
        passport=s.document(DocumentKind.PASSPORT) is not None,
        photo=s.document(DocumentKind.PHOTO) is not None,
        cv=s.document(DocumentKind.CV) is not None,
    )


def render_profile(_: Translator, s: Student, tz: ZoneInfo) -> str:
    return _(
        "profile",
        name=escape(s.full_name),
        group=escape(s.group.name),
        age=age_on(s.birth_date, date.today()),
        birth_date=fmt_date(s.birth_date),
        gender=gender_label(_, s.gender),
        phone=format_phone(s.phone),
        document=document_line(_, s.doc_type, s.doc_number, s.doc_expiry),
        docs=student_docs_line(_, s),
        updated=fmt_dt(s.updated_at, tz),
    )


def render_check(_: Translator, data: dict) -> str:
    doc = data["doc"]
    return _(
        "reg.check",
        last_name=escape(doc["last_name"]),
        first_name=escape(doc["first_name"]),
        middle_name=escape(data.get("middle_name") or "—"),
        birth_date=fmt_date(doc["birth_date"]),
        gender=gender_label(_, doc["gender"]),
        doc_type=_(f"doctype.{doc['doc_type']}"),
        doc_number=f"<code>{escape(doc['doc_number'])}</code>",
        doc_expiry=fmt_date(doc["doc_expiry"]),
        pinfl=f"<code>{escape(doc.get('pinfl') or '—')}</code>",
    )


def form_full_name(data: dict) -> str:
    doc = data["doc"]
    return " ".join(p for p in (doc["last_name"], doc["first_name"], data.get("middle_name")) if p)


def render_review(_: Translator, data: dict) -> str:
    doc = data["doc"]
    return _(
        "reg.review",
        name=escape(form_full_name(data)),
        birth_date=fmt_date(doc["birth_date"]),
        gender=gender_label(_, doc["gender"]),
        document=document_line(_, doc["doc_type"], doc["doc_number"], doc["doc_expiry"]),
        phone=format_phone(data["phone"]),
        group=escape(data.get("group_name") or "—"),
        docs=docs_line(
            _, passport=bool(data.get("passport_files")), photo=bool(data.get("photo_files")), cv=bool(data.get("cv_files"))
        ),
    )


def render_staff_card(_: Translator, s: Student, tz: ZoneInfo) -> str:
    if s.user and s.user.username:
        telegram = f"@{escape(s.user.username)}"
    else:
        telegram = f'<a href="tg://user?id={s.telegram_id}">{s.telegram_id}</a>'
    return _(
        "staff.card",
        name=escape(s.full_name),
        group=escape(s.group.name),
        age=age_on(s.birth_date, date.today()),
        gender=gender_label(_, s.gender),
        birth_date=fmt_date(s.birth_date),
        phone=format_phone(s.phone),
        telegram=telegram,
        document=document_line(_, s.doc_type, s.doc_number, s.doc_expiry),
        pinfl=f"<code>{escape(s.pinfl or '—')}</code>",
        docs=student_docs_line(_, s),
        created=fmt_dt(s.created_at, tz),
        updated=fmt_dt(s.updated_at, tz),
    )


def render_roles(_: Translator, access: Access, leader_groups: list[str]) -> str:
    lines = []
    if access.is_admin:
        lines.append(_("role.admin"))
    if access.is_tutor:
        lines.append(_("role.tutor"))
    if leader_groups:
        lines.append(_("role.leader", groups=", ".join(escape(g) for g in leader_groups)))
    return "\n".join(lines)


def account_roles(_: Translator, account: Account) -> str:
    parts = []
    for r in account.roles:
        if r.role == StaffRole.LEADER:
            parts.append(_("role.leader", groups=escape(r.group.name if r.group else "?")))
        else:
            parts.append(_(f"role.{r.role.value}"))
    return ", ".join(parts) or "—"
