"""Student document files: Telegram files and website uploads."""

from __future__ import annotations

import io
import mimetypes
import time
from pathlib import Path

from aiogram import Bot
from aiogram.types import Message
from sqlalchemy import select

from app.db.models import Document, DocumentKind

MAX_FILE_MB = 20  # Bot API download limit
IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
PDF_MIME = "application/pdf"
WORD_MIMES = {
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.oasis.opendocument.text",
}
# Passports and photos must be images: they are read / checked automatically.
ALLOWED: dict[DocumentKind, set[str]] = {
    DocumentKind.PASSPORT: IMAGE_MIMES,
    DocumentKind.PHOTO: IMAGE_MIMES,
    DocumentKind.CV: IMAGE_MIMES | {PDF_MIME} | WORD_MIMES,
}


class FileRejected(Exception):
    """A file that can't be accepted; ``code`` is a short machine-readable reason."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def is_image(file: dict) -> bool:
    return file.get("mime") in IMAGE_MIMES


def extract_file(message: Message, kind: DocumentKind) -> dict:
    """JSON-serialisable description of the photo/file in ``message``."""
    if message.photo:
        photo = message.photo[-1]  # the largest size Telegram kept
        return {
            "file_id": photo.file_id,
            "unique_id": photo.file_unique_id,
            "type": "photo",
            "mime": "image/jpeg",
            "name": None,
            "size": photo.file_size,
        }
    if message.document:
        doc = message.document
        mime = doc.mime_type or mimetypes.guess_type(doc.file_name or "")[0] or ""
        if mime == "image/jpg":
            mime = "image/jpeg"
        if mime not in ALLOWED[kind]:
            raise FileRejected("type")
        if doc.file_size and doc.file_size > MAX_FILE_MB * 1024 * 1024:
            raise FileRejected("size")
        return {
            "file_id": doc.file_id,
            "unique_id": doc.file_unique_id,
            "type": "document",
            "mime": mime,
            "name": doc.file_name,
            "size": doc.file_size,
        }
    raise FileRejected("expected")


async def download(bot: Bot, file_id: str) -> bytes:
    buf = io.BytesIO()
    await bot.download(file_id, destination=buf)
    return buf.getvalue()


def upload_path(f: dict, uploads_dir: Path) -> Path:
    """Absolute path of a website upload; refuses paths outside ``uploads_dir``."""
    root = uploads_dir.resolve()
    path = (root / f["path"]).resolve()
    if root not in path.parents:
        raise FileNotFoundError(f["path"])
    return path


def read_upload(f: dict, uploads_dir: Path) -> bytes:
    return upload_path(f, uploads_dir).read_bytes()


async def fetch_file(bot: Bot, f: dict, uploads_dir: Path) -> bytes:
    """Bytes of a document file wherever it lives (Telegram or our disk)."""
    if f["type"] == "upload":
        return read_upload(f, uploads_dir)
    return await download(bot, f["file_id"])


async def cleanup_uploads(session_factory, uploads_dir: Path, *, min_age_seconds: int = 3600) -> int:
    """Delete website uploads that no document references any more
    (replaced files, deleted students). Returns the number of files removed."""
    if not uploads_dir.exists():
        return 0
    async with session_factory() as s:
        referenced = {
            f["path"]
            for files in (await s.scalars(select(Document.files))).all()
            for f in files
            if f.get("type") == "upload"
        }
    removed = 0
    now = time.time()
    root = uploads_dir.resolve()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.relative_to(root).as_posix() not in referenced and now - path.stat().st_mtime > min_age_seconds:
            path.unlink(missing_ok=True)
            removed += 1
    return removed
