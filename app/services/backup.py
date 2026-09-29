"""Daily backups: the database and website uploads in one encrypted zip.

The archive is kept on the server (``BACKUP_DIR``, pruned after
``BACKUP_KEEP_DAYS``) and sent by the bot to every admin. With
``BACKUP_PASSWORD`` set it is AES-256 encrypted; 7-Zip, WinRAR or Keka open it.

Students' photos and documents sent through the bot stay on Telegram: the
database keeps their file ids, which work with this bot's token.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pyzipper
from aiogram import Bot
from aiogram.types import FSInputFile
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db import repo
from app.db.models import Account, Group, Staff, StaffRole, Student, User
from app.i18n import t

log = logging.getLogger(__name__)

TELEGRAM_LIMIT = 50 * 1024 * 1024  # bots can't send bigger files
PREFIX = "ttpu-backup-"


class BackupError(Exception):
    pass


@dataclass(slots=True)
class Backup:
    path: Path
    size: int
    students: int
    groups: int
    encrypted: bool


# ------------------------------------------------------------------ creating


async def _dump_postgres(url: str, target: Path) -> None:
    u = make_url(url)
    env = {**os.environ, "PGPASSWORD": u.password or ""}
    args = [
        "pg_dump", "--no-owner", "--no-privileges", "--clean", "--if-exists",
        "-h", u.host or "localhost", "-p", str(u.port or 5432), "-U", u.username or "postgres",
        "-f", str(target), u.database or "",
    ]
    proc = await asyncio.create_subprocess_exec(*args, env=env, stderr=asyncio.subprocess.PIPE)
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise BackupError(f"pg_dump failed: {err.decode(errors='replace').strip()[:500]}")


def _dump_sqlite(url: str, target: Path) -> None:
    source = sqlite3.connect(make_url(url).database)
    try:
        with sqlite3.connect(target) as copy:
            source.backup(copy)  # consistent copy even while the bot writes
    finally:
        source.close()


def _zip(target: Path, files: list[tuple[Path, str]], uploads: Path, password: str | None) -> None:
    kwargs = {"encryption": pyzipper.WZ_AES} if password else {}
    with pyzipper.AESZipFile(target, "w", compression=pyzipper.ZIP_DEFLATED, **kwargs) as zf:
        if password:
            zf.setpassword(password.encode())
        for path, name in files:
            zf.write(path, name)
        if uploads.is_dir():
            for path in sorted(uploads.rglob("*")):
                if path.is_file():
                    zf.write(path, f"uploads/{path.relative_to(uploads)}")


async def create_backup(settings: Settings, sessions: async_sessionmaker[AsyncSession]) -> Backup:
    backup_dir = settings.backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(ZoneInfo(settings.timezone)).strftime("%Y-%m-%d_%H%M")
    target = backup_dir / f"{PREFIX}{stamp}.zip"
    password = settings.backup_password.get_secret_value() if settings.backup_password else None

    async with sessions() as s:
        students = await s.scalar(select(func.count(Student.id))) or 0
        groups = await s.scalar(select(func.count(Group.id))) or 0

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        url = settings.database_url
        if url.startswith("postgresql"):
            dump = tmp_dir / "database.sql"
            await _dump_postgres(url, dump)
        elif url.startswith("sqlite"):
            dump = tmp_dir / "database.sqlite3"
            await asyncio.to_thread(_dump_sqlite, url, dump)
        else:
            raise BackupError(f"Unsupported database: {make_url(url).drivername}")
        partial = target.with_suffix(".zip.part")
        await asyncio.to_thread(_zip, partial, [(dump, dump.name)], settings.uploads_dir, password)
        partial.replace(target)  # a half-written file is never taken for a backup
    os.chmod(target, 0o600)

    async with sessions() as s:
        await repo.audit(s, "system", "backup.create", summary=f"{target.name} · {target.stat().st_size // 1024} KB")
        await s.commit()
    log.info("Backup created: %s (%d bytes)", target, target.stat().st_size)
    return Backup(target, target.stat().st_size, students, groups, encrypted=bool(password))


def prune(backup_dir: Path, keep_days: int, now: datetime | None = None) -> list[Path]:
    """Delete backups older than ``keep_days``; the newest one is always kept."""
    files = sorted(backup_dir.glob(f"{PREFIX}*.zip"), key=lambda p: p.stat().st_mtime)
    cutoff = (now or datetime.now()).timestamp() - keep_days * 86400
    removed = [p for p in files[:-1] if p.stat().st_mtime < cutoff]
    for p in removed:
        p.unlink(missing_ok=True)
    for p in backup_dir.glob(f"{PREFIX}*.zip.part"):  # left by a crash
        p.unlink(missing_ok=True)
    return removed


# ------------------------------------------------------------------ sending


async def admin_chats(settings: Settings, session: AsyncSession) -> list[int]:
    """Telegram IDs of ADMIN_IDS and of active admin accounts linked to Telegram."""
    rows = await session.scalars(
        select(Account.telegram_id)
        .join(Staff, Staff.account_id == Account.id)
        .where(Staff.role == StaffRole.ADMIN, Account.is_active.is_(True), Account.telegram_id.is_not(None))
    )
    return list(dict.fromkeys([*settings.admin_ids, *(tg for tg in rows.all() if tg)]))


async def send_backup(bot: Bot, backup: Backup, chat_ids: list[int], sessions: async_sessionmaker[AsyncSession]) -> int:
    """Send the archive to each chat, in the chat's language. Returns how many got it."""
    sent = 0
    file_id: str | None = None
    for chat_id in chat_ids:
        lang = await _language(sessions, chat_id)
        caption = t(
            lang,
            "backup.caption",
            name=backup.path.name,
            students=backup.students,
            groups=backup.groups,
            size=_size(backup.size),
        ) + "\n" + t(lang, "backup.encrypted" if backup.encrypted else "backup.not_encrypted")
        try:
            if backup.size > TELEGRAM_LIMIT:
                await bot.send_message(chat_id, caption + "\n\n" + t(lang, "backup.too_big"))
            else:
                msg = await bot.send_document(chat_id, file_id or FSInputFile(backup.path), caption=caption)
                file_id = file_id or msg.document.file_id  # upload once, then reuse
            sent += 1
        except Exception as e:  # blocked the bot, never opened it, etc.
            log.warning("Could not send the backup to %s: %s", chat_id, e)
    return sent


async def _language(sessions: async_sessionmaker[AsyncSession], chat_id: int):
    async with sessions() as s:
        user = await s.get(User, chat_id)
    return user.language if user else None


def _size(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB" if n >= 1024 * 1024 else f"{max(1, n // 1024)} KB"


async def run_backup(bot: Bot, settings: Settings, sessions: async_sessionmaker[AsyncSession], chat_ids: list[int] | None = None) -> Backup:
    backup = await create_backup(settings, sessions)
    removed = prune(settings.backup_dir, settings.backup_keep_days)
    if removed:
        log.info("Removed %d old backups", len(removed))
    if chat_ids is None:
        async with sessions() as s:
            chat_ids = await admin_chats(settings, s)
    await send_backup(bot, backup, chat_ids, sessions)
    return backup


# ------------------------------------------------------------------ schedule


def next_run(now: datetime, at: time) -> datetime:
    run = now.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    return run if run > now else run + timedelta(days=1)


async def backup_loop(bot: Bot, settings: Settings, sessions: async_sessionmaker[AsyncSession]) -> None:
    tz = ZoneInfo(settings.timezone)
    at = time.fromisoformat(settings.backup_time)
    while True:
        now = datetime.now(tz)
        await asyncio.sleep((next_run(now, at) - now).total_seconds())
        try:
            await run_backup(bot, settings, sessions)
        except Exception:
            log.exception("Daily backup failed")
            async with sessions() as s:
                chats = await admin_chats(settings, s)
            for chat_id in chats:
                try:
                    await bot.send_message(chat_id, t(await _language(sessions, chat_id), "backup.failed"))
                except Exception:
                    pass
        await asyncio.sleep(60)  # don't run twice within the same minute
