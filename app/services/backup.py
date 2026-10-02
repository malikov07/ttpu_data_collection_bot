"""Daily backups: the database and every student file in one encrypted zip.

The archive holds the database dump, ``students.xlsx``, the website uploads as
stored (``uploads/``, for restoring) and every student's passport, photo, CV and
certificates under ``files/<group>/<student>/``. Files sent through the bot live
on Telegram, so they are downloaded once into ``Settings.telegram_files_dir``
and reused by later backups.

The archive is kept on the server (``BACKUP_DIR``, pruned after
``BACKUP_KEEP_DAYS``) and sent by the bot to every admin, split into parts when
it is bigger than Telegram allows. With ``BACKUP_PASSWORD`` set it is AES-256
encrypted; 7-Zip, WinRAR or Keka open it.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import mimetypes
import os
import re
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
from app.services import documents
from app.services.export import students_xlsx

log = logging.getLogger(__name__)

PART_SIZE = 45 * 1024 * 1024  # bots can't send files over 50 MB
PREFIX = "ttpu-backup-"
MISSING = "missing-files.txt"
DOWNLOADS = 4  # Telegram files downloaded at a time


class BackupError(Exception):
    pass


@dataclass(slots=True)
class Backup:
    path: Path
    size: int
    students: int
    groups: int
    encrypted: bool
    files: int = 0
    missing: int = 0


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


def _safe(text: str) -> str:
    """``text`` as a file or folder name that works on Windows, macOS and Linux."""
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", text).strip(" .")[:80] or "_"


def _ext(f: dict) -> str:
    suffix = Path(f.get("name") or "").suffix.lower()
    if suffix:
        return suffix
    if f.get("mime") == "image/jpeg":
        return ".jpg"
    return mimetypes.guess_extension(f.get("mime") or "") or ""


def student_files(students: list[Student]) -> list[tuple[str, dict]]:
    """(name in the archive, file) for every document and certificate file."""
    out: list[tuple[str, dict]] = []
    for s in sorted(students, key=lambda s: (s.group.name, s.full_name.casefold())):
        folder = f"files/{_safe(s.group.name)}/{_safe(s.full_name)} [{s.id}]"
        for doc in s.documents:
            for i, f in enumerate(doc.files, start=1):
                part = f.get("side") or (str(i) if len(doc.files) > 1 else "")
                out.append((f"{folder}/{doc.kind.value}{'-' + part if part else ''}{_ext(f)}", f))
        for c in s.certificates:
            base = _safe(f"certificate {c.id} - {c.type.value} {c.result} ({c.status.value})")
            for i, f in enumerate(c.files, start=1):
                out.append((f"{folder}/{base}{f' {i}' if len(c.files) > 1 else ''}{_ext(f)}", f))
    return out


def _cache_name(f: dict) -> str:
    # file_unique_id is the same for every bot and never changes; file_id may.
    return f.get("unique_id") or hashlib.sha256(f["file_id"].encode()).hexdigest()[:32]


async def gather_files(
    bot: Bot, entries: list[tuple[str, dict]], uploads_dir: Path, cache: Path
) -> tuple[list[tuple[Path, str]], list[str]]:
    """Local paths of the files in ``entries``, downloading Telegram files not yet
    in ``cache``. Returns (path, name in the archive) pairs and the names that
    could not be found. Cached files no student refers to any more are deleted."""
    cache.mkdir(parents=True, exist_ok=True)
    os.chmod(cache, 0o700)  # passport scans
    limit = asyncio.Semaphore(DOWNLOADS)

    async def local(f: dict) -> Path:
        if f.get("type") == "upload":
            return documents.upload_path(f, uploads_dir)
        path = cache / _cache_name(f)
        if not path.exists():
            async with limit:
                data = await documents.download(bot, f["file_id"])
            part = path.with_name(path.name + ".part")
            part.write_bytes(data)
            part.replace(path)
        return path

    async def one(name: str, f: dict) -> tuple[Path | None, str]:
        try:
            path = await local(f)
            return (path, name) if path.is_file() else (None, name)
        except Exception as e:  # deleted on Telegram, bot token changed, …
            log.warning("Backup: could not get %s: %s", name, e)
            return None, name

    results = await asyncio.gather(*(one(name, f) for name, f in entries))
    keep = {_cache_name(f) for _, f in entries if f.get("type") != "upload"}
    for path in cache.iterdir():
        if path.name not in keep:
            path.unlink(missing_ok=True)
    found = [(path, name) for path, name in results if path is not None]
    return found, [name for path, name in results if path is None]


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


async def create_backup(bot: Bot, settings: Settings, sessions: async_sessionmaker[AsyncSession]) -> Backup:
    backup_dir = settings.backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(ZoneInfo(settings.timezone)).strftime("%Y-%m-%d_%H%M")
    target = backup_dir / f"{PREFIX}{stamp}.zip"
    password = settings.backup_password.get_secret_value() if settings.backup_password else None

    async with sessions() as s:
        students = list((await s.scalars(select(Student).options(*repo.student_options()))).all())
        groups = await s.scalar(select(func.count(Group.id))) or 0
    files, missing = await gather_files(bot, student_files(students), settings.uploads_dir, settings.telegram_files_dir)

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
        sheet = tmp_dir / "students.xlsx"
        sheet.write_bytes(students_xlsx(students, "en"))
        extra = [(dump, dump.name), (sheet, sheet.name)]
        if missing:
            (tmp_dir / MISSING).write_text("Not found on Telegram or on the server:\n" + "\n".join(missing) + "\n")
            extra.append((tmp_dir / MISSING, MISSING))
        partial = target.with_suffix(".zip.part")
        await asyncio.to_thread(_zip, partial, extra + files, settings.uploads_dir, password)
        partial.replace(target)  # a half-written file is never taken for a backup
    os.chmod(target, 0o600)

    size = target.stat().st_size
    async with sessions() as s:
        summary = f"{target.name} · {size // 1024} KB · {len(files)} files" + (f" · {len(missing)} missing" if missing else "")
        await repo.audit(s, "system", "backup.create", summary=summary)
        await s.commit()
    log.info("Backup created: %s (%d bytes, %d files, %d missing)", target, size, len(files), len(missing))
    return Backup(target, size, len(students), groups, encrypted=bool(password), files=len(files), missing=len(missing))


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


def split(path: Path, folder: Path, size: int = PART_SIZE) -> list[Path]:
    """``path`` as ``name.001``, ``name.002``… in ``folder``: the split archive
    7-Zip and Keka open from the first part."""
    parts = []
    with path.open("rb") as src:
        while chunk := src.read(size):
            part = folder / f"{path.name}.{len(parts) + 1:03d}"
            part.write_bytes(chunk)
            parts.append(part)
    return parts


async def send_backup(bot: Bot, backup: Backup, chat_ids: list[int], sessions: async_sessionmaker[AsyncSession]) -> int:
    """Send the archive to each chat, in the chat's language. Returns how many got it."""
    with tempfile.TemporaryDirectory() as tmp:
        parts = [backup.path] if backup.size <= PART_SIZE else await asyncio.to_thread(split, backup.path, Path(tmp), PART_SIZE)
        return await _send_parts(bot, backup, parts, chat_ids, sessions)


async def _send_parts(
    bot: Bot, backup: Backup, parts: list[Path], chat_ids: list[int], sessions: async_sessionmaker[AsyncSession]
) -> int:
    sent = 0
    file_ids: list[str | None] = [None] * len(parts)  # upload each part once, then reuse
    for chat_id in chat_ids:
        lang = await _language(sessions, chat_id)
        lines = [
            t(lang, "backup.caption", name=backup.path.name, students=backup.students, groups=backup.groups,
              files=backup.files, size=_size(backup.size)),
            t(lang, "backup.encrypted" if backup.encrypted else "backup.not_encrypted"),
        ]
        if backup.missing:
            lines.append(t(lang, "backup.missing", count=backup.missing, file=MISSING))
        if len(parts) > 1:
            lines.append(t(lang, "backup.parts", count=len(parts), first=parts[0].name))
        try:
            for i, part in enumerate(parts):
                msg = await bot.send_document(chat_id, file_ids[i] or FSInputFile(part), caption="\n".join(lines) if i == 0 else None)
                file_ids[i] = file_ids[i] or msg.document.file_id
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
    backup = await create_backup(bot, settings, sessions)
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
