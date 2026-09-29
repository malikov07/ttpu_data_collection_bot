"""Request dependencies: DB session, current account, permission checks."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated, AsyncIterator

from aiogram import Bot
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import repo
from app.db.models import Account, WebSession, utcnow
from app.db.repo import Access

SESSION_COOKIE = "ttpu_session"
CSRF_HEADER = "x-requested-with"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_bot(request: Request) -> Bot:
    return request.app.state.bot


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessions() as session:
        yield session


DB = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
BotDep = Annotated[Bot, Depends(get_bot)]


@dataclass(slots=True)
class Principal:
    account: Account
    access: Access
    session_hash: str

    @property
    def username(self) -> str:
        return self.account.username

    def can_edit_group(self, group_id: int) -> bool:
        return self.access.can_edit_group(group_id)


async def session_principal(request: Request, session: DB) -> Principal:
    """The signed-in account (password change may still be pending)."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_authenticated")
    token_hash = hash_token(token)
    row = await session.get(WebSession, token_hash)
    if row is None or repo.as_utc(row.expires_at) < utcnow():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session_expired")
    account = await repo.get_account(session, row.account_id)
    # Roles are re-read on every request, so revoking access is immediate.
    access = repo.access_for(account)
    if account is None or not account.is_active or not access.is_staff:
        await session.delete(row)
        await session.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_authorized")
    if repo.as_utc(row.last_seen_at) < utcnow() - timedelta(minutes=5):
        row.last_seen_at = utcnow()
        await session.commit()
    return Principal(account=account, access=access, session_hash=token_hash)


async def staff_principal(principal: Annotated[Principal, Depends(session_principal)]) -> Principal:
    # A temporary password must be replaced before anything else is allowed.
    if principal.account.must_change_password:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "password_change_required")
    return principal


async def admin_principal(principal: Annotated[Principal, Depends(staff_principal)]) -> Principal:
    if not principal.access.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin_only")
    return principal


def csrf_protect(request: Request) -> None:
    """State-changing requests must carry a custom header.

    Browsers never add custom headers to cross-site form posts, and CORS is
    not enabled, so together with the SameSite cookie this blocks CSRF.
    """
    if request.method not in ("GET", "HEAD", "OPTIONS") and not request.headers.get(CSRF_HEADER):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "csrf")


AnyUser = Annotated[Principal, Depends(session_principal)]
StaffUser = Annotated[Principal, Depends(staff_principal)]
AdminUser = Annotated[Principal, Depends(admin_principal)]
