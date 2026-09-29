"""Sign in with login + password, sign out, change password, current user."""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from collections import defaultdict, deque
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.db import repo
from app.db.models import StaffRole, WebSession, utcnow
from app.services.passwords import DUMMY_HASH, password_problem, verify_password
from app.web.deps import DB, SESSION_COOKIE, AnyUser, BotDep, SettingsDep, hash_token

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["auth"])

MAX_FAILURES = 5  # per username or IP within the window
WINDOW = 15 * 60


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def _failures(request: Request) -> defaultdict[str, deque[float]]:
    return request.app.state.login_failures


def _blocked(request: Request, *keys: str) -> bool:
    now = time.monotonic()
    for key in keys:
        q = _failures(request)[key]
        while q and now - q[0] > WINDOW:
            q.popleft()
        if len(q) >= MAX_FAILURES * (4 if key.startswith("ip:") else 1):
            return True
    return False


async def bot_username(request: Request, bot) -> str | None:
    cached = getattr(request.app.state, "bot_username", None)
    if cached:
        return cached
    try:
        me = await bot.me()
    except Exception:
        return None
    request.app.state.bot_username = me.username
    return me.username


@router.get("/config")
async def config(request: Request, bot: BotDep) -> dict:
    return {"bot_username": await bot_username(request, bot)}


class Login(BaseModel):
    username: str
    password: str


@router.post("/auth/login", status_code=204)
async def login(body: Login, request: Request, response: Response, session: DB, settings: SettingsDep) -> None:
    username = body.username.strip().lower()[:64]
    ip = _client_ip(request)
    keys = (f"user:{username}", f"ip:{ip}")
    if _blocked(request, *keys):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_attempts")

    account = await repo.get_account_by_username(session, username)
    # Always run a hash check so timing doesn't reveal whether a login exists.
    ok = await asyncio.to_thread(verify_password, body.password, account.password_hash if account else DUMMY_HASH)
    if not ok or account is None or not account.is_active or not repo.access_for(account).is_staff:
        for key in keys:
            _failures(request)[key].append(time.monotonic())
        await repo.audit(session, username or "?", "auth.login_failed", summary=ip)
        await session.commit()
        log.warning("Failed web login for %r from %s", username, ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")

    _failures(request).pop(keys[0], None)
    token = secrets.token_urlsafe(32)
    ttl = timedelta(days=settings.session_ttl_days)
    session.add(
        WebSession(
            token_hash=hash_token(token),
            account_id=account.id,
            expires_at=utcnow() + ttl,
            user_agent=(request.headers.get("user-agent") or "")[:256],
            ip=ip,
        )
    )
    account.last_login_at = utcnow()
    await repo.audit(session, account.username, "auth.login", entity="account", entity_id=account.id, summary=ip)
    await session.commit()
    response.set_cookie(
        SESSION_COOKIE, token, max_age=int(ttl.total_seconds()), httponly=True,
        secure=settings.web_secure, samesite="lax", path="/",
    )


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, response: Response, session: DB) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token and (row := await session.get(WebSession, hash_token(token))):
        await session.delete(row)
        await session.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.post("/auth/password", status_code=204)
async def change_password(body: PasswordChange, user: AnyUser, session: DB) -> None:
    ok = await asyncio.to_thread(verify_password, body.current_password, user.account.password_hash)
    if not ok:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": "current_password", "error": "wrong_password"})
    if problem := password_problem(body.new_password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": "new_password", "error": problem})
    if body.new_password == body.current_password:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": "new_password", "error": "password_same"})
    # Other browsers are signed out; this one stays signed in.
    await repo.set_password(session, user.account, body.new_password, keep_session=user.session_hash)
    await repo.audit(session, user.username, "auth.password_change", entity="account", entity_id=user.account.id)
    await session.commit()


@router.get("/me")
async def me(user: AnyUser) -> dict:
    a = user.account
    return {
        "id": a.id,
        "username": a.username,
        "name": a.display_name,
        "role": user.access.role,
        "is_admin": user.access.is_admin,
        "is_tutor": user.access.is_tutor,
        "leader_groups": sorted(
            ({"id": r.group.id, "name": r.group.name} for r in a.roles if r.role == StaffRole.LEADER and r.group),
            key=lambda g: g["name"],
        ),
        "must_change_password": a.must_change_password,
        "telegram_connected": a.telegram_id is not None,
    }
