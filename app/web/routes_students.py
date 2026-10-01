"""Students: list/filter/sort, detail, edit, documents, delete, export."""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import and_, exists, func, not_, or_, select

from app.db import repo
from app.db.models import AuditLog, DocType, Document, DocumentKind, Gender, Group, Student, User
from app.services import vision
from app.services.documents import ALLOWED, IMAGE_MIMES, MAX_FILE_MB, fetch_file, upload_path
from app.services.export import students_xlsx
from app.services.prefs import load_prefs
from app.services.validators import ValidationError, age_on, normalize_name_part, normalize_phone
from app.web.deps import DB, AdminUser, BotDep, SettingsDep, StaffUser
from app.web.serializers import certificate_json, student_json

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/students", tags=["students"])
export_router = APIRouter(prefix="/api/export", tags=["students"])

SortField = Literal["name", "group", "birth_date", "created", "updated"]
DocsFilter = Literal["complete", "missing"]
SORT_COLUMNS = {
    "name": Student.full_name,
    "group": Group.name,
    "birth_date": Student.birth_date,
    "created": Student.created_at,
    "updated": Student.updated_at,
}


def _has(kind: DocumentKind):
    return exists().where(Document.student_id == Student.id, Document.kind == kind)


def filtered_query(user: StaffUser, *, q: str | None, group_id: int | None, gender: Gender | None, docs: DocsFilter | None):
    stmt = select(Student).join(Group, Group.id == Student.group_id).join(User, User.id == Student.telegram_id)
    if (visible := user.access.visible_group_ids()) is not None:
        stmt = stmt.where(Student.group_id.in_(visible))
    if group_id:
        stmt = stmt.where(Student.group_id == group_id)
    if gender:
        stmt = stmt.where(Student.gender == gender)
    if q and (q := q.strip()):
        needle = q.lower().lstrip("@")
        conds = [
            func.lower(Student.full_name).contains(needle, autoescape=True),
            func.lower(func.coalesce(User.username, "")).contains(needle, autoescape=True),
            func.lower(func.coalesce(Student.doc_number, "")).contains(needle, autoescape=True),
        ]
        digits = "".join(ch for ch in q if ch.isdigit())
        if len(digits) >= 3:
            conds.append(Student.phone.contains(digits, autoescape=True))
            conds.append(func.coalesce(Student.pinfl, "").contains(digits, autoescape=True))
        stmt = stmt.where(or_(*conds))
    if docs:
        complete = and_(_has(DocumentKind.PASSPORT), _has(DocumentKind.PHOTO), _has(DocumentKind.CV))
        stmt = stmt.where(complete if docs == "complete" else not_(complete))
    return stmt


@router.get("")
async def list_students(
    user: StaffUser,
    session: DB,
    q: str | None = None,
    group_id: int | None = None,
    gender: Gender | None = None,
    docs: DocsFilter | None = None,
    sort: SortField = "name",
    order: Literal["asc", "desc"] = "asc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> dict:
    base = filtered_query(user, q=q, group_id=group_id, gender=gender, docs=docs)
    total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
    col = SORT_COLUMNS[sort]
    rows = (
        await session.scalars(
            base.options(*repo.student_options())
            .order_by(col.desc() if order == "desc" else col.asc(), Student.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    today = date.today()
    return {"items": [student_json(s, today=today) for s in rows], "total": total, "page": page, "page_size": page_size}


async def _get_visible(session: DB, user: StaffUser, student_id: int) -> Student:
    student = await repo.get_student(session, student_id)
    if student is None or not user.access.can_view_group(student.group_id):
        # Same answer for "missing" and "not yours": don't leak existence.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "student_not_found")
    return student


@router.get("/{student_id}")
async def get_student(student_id: int, user: StaffUser, session: DB) -> dict:
    student = await _get_visible(session, user, student_id)
    history = (
        await session.scalars(
            select(AuditLog)
            .where(AuditLog.entity == "student", AuditLog.entity_id == student.id)
            .order_by(AuditLog.at.desc())
            .limit(30)
        )
    ).all()
    data = student_json(student)
    data["certificates"] = [certificate_json(c) for c in student.certificates]
    data["can_edit"] = user.can_edit_group(student.group_id)
    data["can_delete"] = user.access.is_admin
    data["history"] = [{"at": h.at.isoformat(), "actor": h.actor, "action": h.action, "details": h.details} for h in history]
    return data


class StudentPatch(BaseModel):
    last_name: str | None = None
    first_name: str | None = None
    middle_name: str | None = None  # "" clears it
    birth_date: date | None = None
    gender: Gender | None = None
    phone: str | None = None
    group_id: int | None = None
    doc_type: DocType | None = None
    doc_number: str | None = None
    doc_expiry: date | None = None
    pinfl: str | None = None


def _invalid(field: str, key: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": field, "error": key})


def _as_json(v):
    return v.isoformat() if isinstance(v, date) else (v.value if hasattr(v, "value") else v)


@router.patch("/{student_id}")
async def update_student(student_id: int, body: StudentPatch, user: StaffUser, session: DB, settings: SettingsDep) -> dict:
    student = await _get_visible(session, user, student_id)
    if not user.can_edit_group(student.group_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot_edit")
    prefs = await load_prefs(session, settings)
    new: dict = {}

    for field in ("last_name", "first_name"):
        if (raw := getattr(body, field)) is not None:
            try:
                new[field] = normalize_name_part(raw)
            except ValidationError:
                raise _invalid(field, "invalid_name") from None
    if body.middle_name is not None:
        try:
            new["middle_name"] = normalize_name_part(body.middle_name) if body.middle_name.strip() else None
        except ValidationError:
            raise _invalid("middle_name", "invalid_name") from None
    if body.birth_date is not None:
        if not prefs.min_student_age <= age_on(body.birth_date, date.today()) <= prefs.max_student_age:
            raise _invalid("birth_date", "invalid_age")
        new["birth_date"] = body.birth_date
    if body.gender is not None:
        new["gender"] = body.gender
    if body.phone is not None:
        try:
            new["phone"] = normalize_phone(body.phone)
        except ValidationError:
            raise _invalid("phone", "invalid_phone") from None
    if body.group_id is not None and body.group_id != student.group_id:
        group = await session.get(Group, body.group_id)
        if group is None or not user.can_edit_group(group.id):
            raise _invalid("group_id", "invalid_group")
        new["group_id"] = group.id
    if body.doc_type is not None:
        new["doc_type"] = body.doc_type
    if body.doc_number is not None:
        number = body.doc_number.strip().upper().replace(" ", "")
        if not re.fullmatch(r"[A-Z0-9]{5,20}", number):
            raise _invalid("doc_number", "invalid_doc_number")
        new["doc_number"] = number
    if body.doc_expiry is not None:
        new["doc_expiry"] = body.doc_expiry
    if body.pinfl is not None:
        pinfl = body.pinfl.strip()
        if pinfl and not re.fullmatch(r"\d{14}", pinfl):
            raise _invalid("pinfl", "invalid_pinfl")
        new["pinfl"] = pinfl or None

    changes: dict[str, list] = {}
    for field, value in new.items():
        old = getattr(student, field)
        if old != value:
            changes["group" if field == "group_id" else field] = [
                student.group.name if field == "group_id" else _as_json(old),
                (await session.get(Group, value)).name if field == "group_id" else _as_json(value),
            ]
            setattr(student, field, value)
    if changes:
        student.set_names(student.last_name, student.first_name, student.middle_name)
        student.updated_at = repo.utcnow()
        await repo.audit(
            session, user.username, "student.edit", entity="student", entity_id=student.id,
            summary=student.full_name, details=changes,
        )
        await session.commit()
    session.expire_all()
    return await get_student(student_id, user, session)


@router.delete("/{student_id}", status_code=204)
async def delete_student(student_id: int, user: AdminUser, session: DB) -> None:
    student = await _get_visible(session, user, student_id)
    summary = f"{student.full_name} · {student.group.name}"
    await repo.delete_student(session, student)
    await repo.audit(session, user.username, "student.delete", entity="student", entity_id=student_id, summary=summary)
    await session.commit()


# ------------------------------------------------------------------ documents


@router.get("/{student_id}/documents/{kind}/{index}")
async def get_document_file(
    student_id: int, kind: DocumentKind, index: int, user: StaffUser, session: DB, settings: SettingsDep,
    bot: BotDep, download: bool = False,
) -> Response:
    student = await _get_visible(session, user, student_id)
    doc = student.document(kind)
    if doc is None or not 0 <= index < len(doc.files):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document_not_found")
    f = doc.files[index]
    try:
        data = await fetch_file(bot, f, settings.uploads_dir)
    except Exception:
        log.exception("Could not fetch document %s/%s/%s", student_id, kind, index)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "file_unavailable") from None
    # Viewing the portrait thumbnail isn't logged; passports and CVs are.
    if kind != DocumentKind.PHOTO:
        await repo.audit(
            session, user.username, "document.view", entity="student", entity_id=student.id,
            summary=f"{kind.value} {index + 1}/{len(doc.files)} · {student.full_name}",
        )
        await session.commit()
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}
    filename = f.get("name") or f"{kind.value}-{student.id}-{index + 1}{ext.get(f.get('mime'), '')}"
    safe_name = "".join(ch for ch in filename if ch.isascii() and (ch.isalnum() or ch in "._- ")) or "document"
    return Response(
        content=data,
        media_type=f.get("mime") or "application/octet-stream",
        headers={
            "Content-Disposition": f'{"attachment" if download else "inline"}; filename="{safe_name}"',
            "Cache-Control": "private, no-store",
        },
    )


_MAGIC = [
    (b"%PDF", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xd0\xcf\x11\xe0", "application/msword"),
]


def sniff_mime(data: bytes, filename: str) -> str | None:
    """File type from its content (magic bytes), not from its name."""
    for magic, mime in _MAGIC:
        if data.startswith(magic):
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"PK\x03\x04"):
        lower = filename.lower()
        if lower.endswith(".docx"):
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if lower.endswith(".odt"):
            return "application/vnd.oasis.opendocument.text"
    return None


@router.post("/{student_id}/documents/{kind}")
async def replace_document(
    student_id: int, kind: DocumentKind, user: StaffUser, session: DB, settings: SettingsDep,
    files: list[UploadFile] = File(...),
) -> dict:
    student = await _get_visible(session, user, student_id)
    if not user.can_edit_group(student.group_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot_edit")
    prefs = await load_prefs(session, settings)
    limit = 1 if kind == DocumentKind.PHOTO else 2 if kind == DocumentKind.PASSPORT else prefs.max_document_pages
    if not files or len(files) > limit:
        raise _invalid("files", "too_many_files")

    entries: list[tuple[dict, bytes]] = []
    for upload in files:
        data = await upload.read(MAX_FILE_MB * 1024 * 1024 + 1)
        if len(data) > MAX_FILE_MB * 1024 * 1024:
            raise _invalid("files", "file_too_large")
        mime = sniff_mime(data, upload.filename or "")
        if mime is None or mime not in ALLOWED[kind]:
            raise _invalid("files", "unsupported_type")
        digest = hashlib.sha256(data).hexdigest()[:32]
        entries.append(
            (
                {
                    "file_id": f"upload:{digest}",
                    "unique_id": f"upload:{digest}",
                    "type": "upload",
                    "mime": mime,
                    "name": (upload.filename or "")[:128] or None,
                    "size": len(data),
                    "path": f"{student.id}/{uuid.uuid4().hex}",
                },
                data,
            )
        )
    if len(entries) > 1 and any(meta["mime"] not in IMAGE_MIMES for meta, _ in entries):
        raise _invalid("files", "mixed_types")
    if kind == DocumentKind.PHOTO and (error := await vision.check_portrait(entries[0][1])):
        raise _invalid("files", f"photo_{error}")

    for meta, data in entries:
        path = upload_path(meta, settings.uploads_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    if repo.set_document_files(student, kind, [meta for meta, _ in entries]):
        student.updated_at = repo.utcnow()
        await repo.audit(
            session, user.username, "document.replace", entity="student", entity_id=student.id,
            summary=f"{kind.value} · {student.full_name}", details={"files": len(entries)},
        )
    await session.commit()
    session.expire_all()
    return await get_student(student_id, user, session)


# ------------------------------------------------------------------ export


@export_router.get("/students.xlsx")
async def export_students(
    user: StaffUser,
    session: DB,
    q: str | None = None,
    group_id: int | None = None,
    gender: Gender | None = None,
    docs: DocsFilter | None = None,
    lang: Literal["uz", "ru", "en"] = "en",
) -> Response:
    stmt = filtered_query(user, q=q, group_id=group_id, gender=gender, docs=docs)
    students = list((await session.scalars(stmt.options(*repo.student_options()))).all())
    data = students_xlsx(students, lang)
    await repo.audit(session, user.username, "students.export", summary=f"{len(students)} rows")
    await session.commit()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="ttpu-students-{date.today().isoformat()}.xlsx"'},
    )
