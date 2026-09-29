"""Staff accounts (admin only): create, roles, disable, reset password, delete."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import repo
from app.db.models import Account, Group, StaffRole
from app.services.passwords import normalize_username
from app.web.deps import DB, AdminUser, Principal
from app.web.serializers import account_json

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _err(code: int, field: str | None, error: str) -> HTTPException:
    return HTTPException(code, {"field": field, "error": error} if field else error)


class RoleIn(BaseModel):
    role: StaffRole
    group_id: int | None = None


async def _roles(session: DB, roles: list[RoleIn]) -> list[tuple[StaffRole, int | None]]:
    if not roles:
        raise _err(422, "roles", "role_required")
    result: list[tuple[StaffRole, int | None]] = []
    for r in roles:
        group_id = None
        if r.role == StaffRole.LEADER:
            if not r.group_id or await session.get(Group, r.group_id) is None:
                raise _err(422, "roles", "group_required")
            group_id = r.group_id
        if (r.role, group_id) not in result:
            result.append((r.role, group_id))
    return result


async def _get(session: DB, account_id: int) -> Account:
    account = await repo.get_account(session, account_id)
    if account is None:
        raise _err(404, None, "account_not_found")
    return account


async def _guard(session: DB, account: Account, user: Principal, *, removing_admin: bool) -> None:
    if account.id == user.account.id:
        raise _err(409, None, "cannot_change_self")
    is_admin = any(r.role == StaffRole.ADMIN for r in account.roles) and account.is_active
    if removing_admin and is_admin and await repo.count_admins(session) <= 1:
        raise _err(409, None, "last_admin")


@router.get("")
async def list_accounts(user: AdminUser, session: DB) -> list[dict]:
    return [account_json(a) for a in await repo.list_accounts(session)]


class AccountCreate(BaseModel):
    username: str
    display_name: str | None = None
    roles: list[RoleIn]


@router.post("", status_code=201)
async def create_account(body: AccountCreate, user: AdminUser, session: DB) -> dict:
    username = normalize_username(body.username)
    if username is None:
        raise _err(422, "username", "invalid_username")
    if await repo.get_account_by_username(session, username):
        raise _err(409, "username", "username_taken")
    roles = await _roles(session, body.roles)
    name = (body.display_name or "").strip()[:128] or None
    account, password = await repo.create_account(session, username=username, display_name=name, roles=roles)
    account_id = account.id
    await repo.audit(
        session, user.username, "account.create", entity="account", entity_id=account_id,
        summary=f"{username} · {', '.join(r.value for r, _ in roles)}",
    )
    await session.commit()
    session.expire_all()
    data = account_json(await _get(session, account_id))
    data["temporary_password"] = password  # shown once, never stored in clear text
    return data


class AccountPatch(BaseModel):
    display_name: str | None = None
    roles: list[RoleIn] | None = None
    is_active: bool | None = None


@router.patch("/{account_id}")
async def update_account(account_id: int, body: AccountPatch, user: AdminUser, session: DB) -> dict:
    account = await _get(session, account_id)
    changes: dict[str, list] = {}
    if body.display_name is not None:
        name = body.display_name.strip()[:128] or None
        if name != account.display_name:
            changes["display_name"] = [account.display_name, name]
            account.display_name = name
    if body.roles is not None:
        roles = await _roles(session, body.roles)
        before = sorted(f"{r.role.value}:{r.group_id or ''}" for r in account.roles)
        after = sorted(f"{r.value}:{g or ''}" for r, g in roles)
        if before != after:
            await _guard(session, account, user, removing_admin=not any(r == StaffRole.ADMIN for r, _ in roles))
            repo.set_roles(account, roles)
            changes["roles"] = [before, after]
    if body.is_active is not None and body.is_active != account.is_active:
        await _guard(session, account, user, removing_admin=not body.is_active)
        account.is_active = body.is_active
        changes["is_active"] = [not body.is_active, body.is_active]
        if not body.is_active:
            await repo.end_sessions(session, account.id)
    if changes:
        await repo.audit(
            session, user.username, "account.edit", entity="account", entity_id=account.id,
            summary=account.username, details=changes,
        )
        await session.commit()
    session.expire_all()
    return account_json(await _get(session, account_id))


@router.post("/{account_id}/reset-password")
async def reset_password(account_id: int, user: AdminUser, session: DB) -> dict:
    account = await _get(session, account_id)
    if account.id == user.account.id:
        raise _err(409, None, "cannot_change_self")
    password = await repo.reset_password(session, account)
    await repo.audit(session, user.username, "account.reset_password", entity="account", entity_id=account.id, summary=account.username)
    await session.commit()
    return {"temporary_password": password}


@router.post("/{account_id}/unlink-telegram")
async def unlink_telegram(account_id: int, user: AdminUser, session: DB) -> dict:
    account = await _get(session, account_id)
    if account.telegram_id is not None:
        account.telegram_id = None
        await repo.audit(session, user.username, "account.unlink_telegram", entity="account", entity_id=account.id, summary=account.username)
        await session.commit()
    session.expire_all()
    return account_json(await _get(session, account_id))


@router.delete("/{account_id}", status_code=204)
async def delete_account(account_id: int, user: AdminUser, session: DB) -> None:
    account = await _get(session, account_id)
    await _guard(session, account, user, removing_admin=True)
    username = account.username
    await session.delete(account)
    await repo.audit(session, user.username, "account.delete", entity="account", entity_id=account_id, summary=username)
    await session.commit()
