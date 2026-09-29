"""Staff web panel: JSON API under /api and the built React app everywhere else."""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path

from aiogram import Bot
from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import BASE_DIR, Settings
from app.web import routes_accounts, routes_admin, routes_auth, routes_groups, routes_students
from app.web.deps import csrf_protect

FRONTEND_DIST = BASE_DIR / "web" / "dist"

CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "frame-src 'self' blob:",
        "connect-src 'self'",
        "font-src 'self' data:",
        "object-src 'self' blob:",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)


def create_app(
    *,
    settings: Settings,
    sessions: async_sessionmaker[AsyncSession],
    bot: Bot,
    frontend_dist: Path = FRONTEND_DIST,
) -> FastAPI:
    app = FastAPI(
        title="TTPU Student Data",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        dependencies=[Depends(csrf_protect)],
    )
    app.state.settings = settings
    app.state.sessions = sessions
    app.state.bot = bot
    app.state.login_failures = defaultdict(deque)  # sign-in rate limit per login / IP

    for module in (routes_auth, routes_students, routes_groups, routes_accounts, routes_admin):
        app.include_router(module.router)
    app.include_router(routes_students.export_router)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Content-Security-Policy", CSP)
        if settings.web_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if request.url.path.startswith("/api/") or exc.status_code != 404:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
        return _index(frontend_dist)

    @app.get("/api/health", include_in_schema=False)
    async def health() -> dict:
        return {"ok": True}

    assets = frontend_dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "not_found"}, status_code=404)
        candidate = (frontend_dist / path).resolve()
        if path and candidate.is_file() and frontend_dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return _index(frontend_dist)

    return app


def _index(frontend_dist: Path):
    index = frontend_dist / "index.html"
    if index.is_file():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return HTMLResponse(
        "<h1>TTPU Student Data</h1><p>The web app is not built yet. Run <code>npm run build</code> in <code>web/</code>.</p>",
        status_code=200,
    )
