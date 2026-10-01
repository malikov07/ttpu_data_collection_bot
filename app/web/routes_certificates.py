"""Certificates students sent in the bot: list, view files, accept or reject."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.db import repo
from app.db.models import Certificate, CertStatus, CertType, Student
from app.services import certificates as certs
from app.services.documents import fetch_file
from app.web.deps import DB, BotDep, SettingsDep, StaffUser
from app.web.serializers import certificate_json

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/certificates", tags=["certificates"])


def _scoped(user: StaffUser):
    stmt = select(Certificate).join(Student, Student.id == Certificate.student_id)
    if (visible := user.access.visible_group_ids()) is not None:
        stmt = stmt.where(Student.group_id.in_(visible))
    return stmt


@router.get("")
async def list_certificates(
    user: StaffUser,
    session: DB,
    status_: CertStatus | None = Query(None, alias="status"),
    type_: CertType | None = Query(None, alias="type"),
    group_id: int | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> dict:
    stmt = _scoped(user)
    if type_:
        stmt = stmt.where(Certificate.type == type_)
    if group_id:
        stmt = stmt.where(Student.group_id == group_id)
    if q and (q := q.strip()):
        stmt = stmt.where(func.lower(Student.full_name).contains(q.lower(), autoescape=True))
    # Counts per status for the tabs, with the other filters applied.
    sub = stmt.subquery()
    counts = {CertStatus(k): n for k, n in (await session.execute(select(sub.c.status, func.count()).group_by(sub.c.status))).all()}
    if status_:
        stmt = stmt.where(Certificate.status == status_)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        await session.scalars(
            stmt.options(*repo.certificate_options())
            .order_by(Certificate.created_at.desc(), Certificate.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return {
        "items": [certificate_json(c, student=True, can_review=user.can_edit_group(c.student.group_id)) for c in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "counts": {s.value: counts.get(s, 0) for s in CertStatus},
    }


async def _get_visible(session: DB, user: StaffUser, cert_id: int) -> Certificate:
    cert = await repo.get_certificate(session, cert_id)
    if cert is None or not user.access.can_view_group(cert.student.group_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "certificate_not_found")
    return cert


@router.get("/{cert_id}/files/{index}")
async def get_certificate_file(
    cert_id: int, index: int, user: StaffUser, session: DB, settings: SettingsDep, bot: BotDep, download: bool = False
) -> Response:
    cert = await _get_visible(session, user, cert_id)
    if not 0 <= index < len(cert.files):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document_not_found")
    f = cert.files[index]
    try:
        data = await fetch_file(bot, f, settings.uploads_dir)
    except Exception:
        log.exception("Could not fetch certificate %s/%s", cert_id, index)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "file_unavailable") from None
    await repo.audit(
        session, user.username, "certificate.view", entity="student", entity_id=cert.student_id,
        summary=f"{certs.label('en', cert)} {index + 1}/{len(cert.files)} · {cert.student.full_name}",
    )
    await session.commit()
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}
    filename = f.get("name") or f"certificate-{cert.id}-{index + 1}{ext.get(f.get('mime'), '')}"
    safe_name = "".join(ch for ch in filename if ch.isascii() and (ch.isalnum() or ch in "._- ")) or "certificate"
    return Response(
        content=data,
        media_type=f.get("mime") or "application/octet-stream",
        headers={
            "Content-Disposition": f'{"attachment" if download else "inline"}; filename="{safe_name}"',
            "Cache-Control": "private, no-store",
        },
    )


class Review(BaseModel):
    status: Literal["approved", "rejected"]
    note: str | None = Field(None, max_length=500)


@router.post("/{cert_id}/review")
async def review_certificate(cert_id: int, body: Review, user: StaffUser, session: DB, bot: BotDep) -> dict:
    cert = await _get_visible(session, user, cert_id)
    if not user.can_edit_group(cert.student.group_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot_edit")
    new = CertStatus(body.status)
    note = " ".join((body.note or "").split()) or None
    if (cert.status, cert.note) != (new, note if new == CertStatus.REJECTED else None):
        repo.review_certificate(cert, new, user.username, note)
        await repo.audit(
            session, user.username, "certificate.approve" if new == CertStatus.APPROVED else "certificate.reject",
            entity="student", entity_id=cert.student_id, summary=f"{certs.label('en', cert)} · {cert.student.full_name}",
            details={"reason": note} if note and new == CertStatus.REJECTED else None,
        )
        await session.commit()
        await certs.notify_student(bot, session, cert)
    return certificate_json(cert, student=True, can_review=True)
