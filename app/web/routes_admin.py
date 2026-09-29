"""Dashboard stats (all staff), runtime settings and audit log (admins)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func, or_, select, true
from sqlalchemy.orm import selectinload

from app.db import repo
from app.db.models import AuditLog, DocumentKind, Gender, Group, Student
from app.services.prefs import Prefs, load_prefs, save_prefs
from app.web.deps import DB, AdminUser, SettingsDep, StaffUser

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/stats")
async def stats(user: StaffUser, session: DB, settings: SettingsDep) -> dict:
    visible = user.access.visible_group_ids()
    scope = Student.group_id.in_(visible) if visible is not None else true()

    total = await session.scalar(select(func.count(Student.id)).where(scope)) or 0
    tz = ZoneInfo(settings.timezone)
    today = datetime.now(tz).date()
    start = today - timedelta(days=29)
    since = datetime.combine(start, time.min, tzinfo=tz)
    per_day = {start + timedelta(days=i): 0 for i in range(30)}
    for ts in (await session.scalars(select(Student.created_at).where(scope, Student.created_at >= since))).all():
        day = repo.as_utc(ts).astimezone(tz).date()
        if day in per_day:
            per_day[day] += 1

    genders = dict((await session.execute(select(Student.gender, func.count()).where(scope).group_by(Student.gender))).all())

    students = (await session.scalars(select(Student).where(scope).options(selectinload(Student.documents)))).all()
    docs = {"complete": 0, "no_photo": 0, "no_cv": 0}
    for s in students:
        kinds = {d.kind for d in s.documents}
        if DocumentKind.PHOTO not in kinds:
            docs["no_photo"] += 1
        if DocumentKind.CV not in kinds:
            docs["no_cv"] += 1
        if kinds >= set(DocumentKind):
            docs["complete"] += 1

    group_stmt = select(Group.id, Group.name, func.count(Student.id)).outerjoin(Student, Student.group_id == Group.id)
    group_stmt = group_stmt.where(Group.id.in_(visible)) if visible is not None else group_stmt.where(Group.is_active.is_(True))
    by_group = (await session.execute(group_stmt.group_by(Group.id, Group.name).order_by(Group.name))).all()

    return {
        "students": total,
        "groups": len(by_group),
        "today": per_day[today],
        "last_7_days": sum(v for d, v in per_day.items() if d > today - timedelta(days=7)),
        "per_day": [{"date": d.isoformat(), "count": n} for d, n in per_day.items()],
        "gender": {g.value: genders.get(g, 0) for g in Gender},
        "documents": docs,
        "by_group": [{"id": gid, "name": name, "students": n} for gid, name, n in by_group],
    }


@router.get("/settings")
async def get_settings_route(user: AdminUser, session: DB, settings: SettingsDep) -> dict:
    prefs = await load_prefs(session, settings)
    return {"prefs": prefs.model_dump(), "environment": {"timezone": settings.timezone}}


@router.put("/settings")
async def put_settings(body: dict, user: AdminUser, session: DB, settings: SettingsDep) -> dict:
    current = await load_prefs(session, settings)
    try:
        new = Prefs(**{**current.model_dump(), **body})
    except PydanticValidationError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"error": "invalid_settings"}) from None
    changes = {k: [v, getattr(new, k)] for k, v in current.model_dump().items() if getattr(new, k) != v}
    if changes:
        await save_prefs(session, new)
        await repo.audit(session, user.username, "settings.edit", details=changes)
        await session.commit()
    return await get_settings_route(user, session, settings)


@router.get("/audit")
async def audit_log(
    user: AdminUser,
    session: DB,
    q: str | None = None,
    action: str | None = None,
    actor: str | None = None,
    since: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict:
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action.startswith(action, autoescape=True))
    if actor:
        stmt = stmt.where(AuditLog.actor == actor)
    if since:
        stmt = stmt.where(AuditLog.at >= datetime.combine(since, time.min))
    if q and (q := q.strip()):
        stmt = stmt.where(
            or_(
                func.lower(AuditLog.summary).contains(q.lower(), autoescape=True),
                func.lower(AuditLog.actor).contains(q.lower(), autoescape=True),
            )
        )
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        await session.scalars(stmt.order_by(AuditLog.at.desc(), AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size))
    ).all()
    return {
        "items": [
            {
                "id": r.id, "at": r.at.isoformat(), "actor": r.actor, "action": r.action, "entity": r.entity,
                "entity_id": r.entity_id, "summary": r.summary, "details": r.details,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
