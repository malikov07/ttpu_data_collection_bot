"""Groups: list (scoped), add, import from EduPage, rename, hide/show, delete."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db import repo
from app.db.models import Account, Group, Staff, StaffRole, Student
from app.services import edupage
from app.services.validators import parse_group_names
from app.web.deps import DB, AdminUser, SettingsDep, StaffUser
from app.web.serializers import group_json

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/groups", tags=["groups"])


async def _payload(session: DB, group_ids: list[int] | None, *, include_inactive: bool) -> list[dict]:
    counts = dict((await session.execute(select(Student.group_id, func.count(Student.id)).group_by(Student.group_id))).all())
    stmt = select(Group).order_by(Group.name)
    if group_ids is not None:
        stmt = stmt.where(Group.id.in_(group_ids))
    elif not include_inactive:
        stmt = stmt.where(Group.is_active.is_(True))
    groups = (await session.scalars(stmt)).all()
    roles = (
        await session.scalars(
            select(Staff).where(Staff.role == StaffRole.LEADER).options(selectinload(Staff.account))
        )
    ).all()
    leaders: dict[int, list[Account]] = {}
    for r in roles:
        if r.account.is_active:
            leaders.setdefault(r.group_id, []).append(r.account)
    return [group_json(g, students=counts.get(g.id, 0), leaders=leaders.get(g.id, [])) for g in groups]


@router.get("")
async def list_groups(user: StaffUser, session: DB, include_inactive: bool = False) -> list[dict]:
    return await _payload(session, user.access.visible_group_ids(), include_inactive=include_inactive and user.access.is_admin)


class GroupsCreate(BaseModel):
    names: str  # one per line or comma-separated


@router.post("")
async def add_groups(body: GroupsCreate, user: AdminUser, session: DB) -> dict:
    parsed = parse_group_names(body.names)
    if parsed.invalid and not parsed.valid:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": "names", "error": "invalid_names", "names": parsed.invalid}
        )
    added, existing = await repo.add_groups(session, parsed.valid)
    if added:
        await repo.audit(session, user.username, "group.add", entity="group", summary=", ".join(added))
    await session.commit()
    return {"added": added, "existing": existing, "invalid": parsed.invalid}


@router.post("/import")
async def import_from_edupage(user: AdminUser, session: DB, settings: SettingsDep) -> dict:
    """Add the groups listed in the public EduPage timetable (nothing is removed)."""
    if not settings.edupage_url:
        raise HTTPException(status.HTTP_409_CONFLICT, "edupage_disabled")
    try:
        names = await edupage.fetch_group_names(settings.edupage_url)
    except edupage.EdupageError as e:
        log.warning("EduPage import failed: %s", e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "edupage_unavailable") from e
    result = await repo.import_groups(session, names)
    await repo.audit(
        session, user.username, "group.import", entity="group",
        summary=f"EduPage: +{len(result.added)}", details={"added": ", ".join(result.added)} if result.added else None,
    )
    await session.commit()
    return {"added": result.added, "existing": result.existing, "missing": result.missing}


class GroupPatch(BaseModel):
    name: str | None = None
    is_active: bool | None = None


@router.patch("/{group_id}")
async def update_group(group_id: int, body: GroupPatch, user: AdminUser, session: DB) -> dict:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group_not_found")
    changes: dict[str, list] = {}
    if body.name is not None:
        parsed = parse_group_names(body.name)
        if len(parsed.valid) != 1 or parsed.invalid:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": "name", "error": "invalid_name"})
        new_name = parsed.valid[0]
        other = await repo.get_group_by_name(session, new_name)
        if other is not None and other.id != group.id:
            raise HTTPException(status.HTTP_409_CONFLICT, {"field": "name", "error": "name_taken"})
        if new_name != group.name:
            changes["name"] = [group.name, new_name]
            group.name = new_name
    if body.is_active is not None and body.is_active != group.is_active:
        changes["is_active"] = [group.is_active, body.is_active]
        group.is_active = body.is_active
    if changes:
        await repo.audit(session, user.username, "group.edit", entity="group", entity_id=group.id, summary=group.name, details=changes)
        await session.commit()
    return (await _payload(session, [group.id], include_inactive=True))[0]


@router.delete("/{group_id}")
async def delete_group(group_id: int, user: AdminUser, session: DB) -> dict:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group_not_found")
    name = group.name
    deleted = await repo.remove_group(session, group)
    await repo.audit(session, user.username, "group.delete" if deleted else "group.hide", entity="group", entity_id=group_id, summary=name)
    await session.commit()
    return {"deleted": deleted}
