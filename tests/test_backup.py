"""Backups: encrypted archive of the database and all student files, pruning, sending."""

from __future__ import annotations

import os
import sqlite3
import time as systime
from datetime import datetime, time

import pyzipper
import pytest
from aiogram import methods
from pydantic import SecretStr

from app.db import repo
from app.db.models import CertType, DocumentKind, StaffRole
from app.services import backup, documents
from tests.test_flows import register, setup_groups


async def add_group(h, name="SE-24-01"):
    async with h.sessions() as s:
        await repo.add_groups(s, [name])
        await s.commit()


async def test_backup_is_an_encrypted_archive_of_database_and_uploads(h, settings, tmp_path):
    await add_group(h)
    (settings.uploads_dir / "3").mkdir(parents=True)
    (settings.uploads_dir / "3" / "cv.pdf").write_bytes(b"%PDF-1.4 test")
    settings = settings.model_copy(update={"backup_password": SecretStr("S3cret-backup")})

    b = await backup.create_backup(h.bot, settings, h.sessions)
    assert b.path.parent == settings.backup_dir and b.encrypted and b.groups == 1
    assert oct(b.path.stat().st_mode & 0o777) == "0o600"

    with pyzipper.AESZipFile(b.path) as zf:
        with pytest.raises(RuntimeError):  # no password: unreadable
            zf.read("database.sqlite3")
        zf.setpassword(b"S3cret-backup")
        assert zf.read("uploads/3/cv.pdf") == b"%PDF-1.4 test"
        db = tmp_path / "restored.sqlite3"
        db.write_bytes(zf.read("database.sqlite3"))
    with sqlite3.connect(db) as conn:
        assert conn.execute("select name from groups").fetchall() == [("SE-24-01",)]


async def test_backup_holds_every_student_file(h, settings, monkeypatch):
    downloads: list[str] = []

    async def fake_download(bot, file_id: str) -> bytes:
        downloads.append(file_id)
        if file_id == "gone":
            raise RuntimeError("Bad Request: wrong file_id")
        return f"data:{file_id}".encode()

    monkeypatch.setattr(documents, "download", fake_download)
    await setup_groups(h)
    await register(h, uid=100, group="SE-24-01")  # passport, photo and CV through the bot
    (settings.uploads_dir / "1").mkdir(parents=True)
    (settings.uploads_dir / "1" / "x.pdf").write_bytes(b"%PDF web")
    async with h.sessions() as s:
        student = await repo.get_student_by_tg(s, 100)
        repo.set_document_files(student, DocumentKind.CV, [
            {"file_id": "upload:x", "unique_id": "upload:x", "type": "upload", "path": "1/x.pdf", "mime": "application/pdf", "name": "my cv.pdf"}
        ])
        await repo.add_certificate(s, student, CertType.IELTS, "7.5", [
            {"file_id": "ielts-1", "unique_id": "u-ielts-1", "type": "photo", "mime": "image/jpeg"},
            {"file_id": "gone", "unique_id": "u-gone", "type": "photo", "mime": "image/jpeg"},
        ])
        await s.commit()
        folder = f"files/SE-24-01/{student.full_name} [{student.id}]"

    b = await backup.create_backup(h.bot, settings, h.sessions)
    assert (b.students, b.files, b.missing) == (1, 4, 1)
    with pyzipper.AESZipFile(b.path) as zf:
        names = set(zf.namelist())
        assert zf.read(f"{folder}/passport-main.jpg") == b"data:pass-100"
        assert zf.read(f"{folder}/photo.jpg") == b"data:face-100"
        assert zf.read(f"{folder}/cv.pdf") == b"%PDF web"  # website upload replaced the bot's CV
        assert zf.read(f"{folder}/certificate 1 - ielts 7.5 (pending) 1.jpg") == b"data:ielts-1"
        assert f"{folder}/certificate 1 - ielts 7.5 (pending) 2.jpg" in zf.read(backup.MISSING).decode()
        assert {"database.sqlite3", "students.xlsx", "uploads/1/x.pdf"} <= names

    # Downloaded once; files no student uses any more leave the cache.
    assert sorted(p.name for p in settings.telegram_files_dir.iterdir()) == ["u-face-100", "u-ielts-1", "u-pass-100"]
    downloads.clear()
    await backup.create_backup(h.bot, settings, h.sessions)
    assert downloads == ["gone"]

    # Missing files are reported to admins.
    h.tg.clear()
    await backup.send_backup(h.bot, b, [1], h.sessions)
    assert "1 files could not be downloaded" in h.tg.last(methods.SendDocument).caption


async def test_big_backups_are_sent_in_parts(h, tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "PART_SIZE", 10)
    archive = tmp_path / f"{backup.PREFIX}big.zip"
    archive.write_bytes(bytes(range(25)))
    b = backup.Backup(archive, 25, students=1, groups=1, encrypted=True)
    assert await backup.send_backup(h.bot, b, [1, 2], h.sessions) == 2
    sent = [r for r in h.tg.requests if isinstance(r, methods.SendDocument)]
    assert [r.chat_id for r in sent] == [1, 1, 1, 2, 2, 2]
    assert [r.document.filename for r in sent[:3]] == [f"{archive.name}.00{i}" for i in (1, 2, 3)]
    assert all(isinstance(r.document, str) for r in sent[3:])  # uploaded once, then resent by file id
    assert f"{archive.name}.001" in sent[0].caption and sent[1].caption is None

    parts = backup.split(archive, tmp_path, size=10)
    assert b"".join(p.read_bytes() for p in parts) == archive.read_bytes()


async def test_old_backups_are_pruned_but_the_newest_is_kept(tmp_path):
    now = systime.time()
    for age_days, name in [(40, "a"), (31, "b"), (5, "c")]:
        p = tmp_path / f"{backup.PREFIX}{name}.zip"
        p.write_bytes(b"x")
        os.utime(p, (now - age_days * 86400, now - age_days * 86400))
    (tmp_path / f"{backup.PREFIX}crash.zip.part").write_bytes(b"x")
    removed = backup.prune(tmp_path, keep_days=30)
    assert sorted(p.name for p in removed) == [f"{backup.PREFIX}a.zip", f"{backup.PREFIX}b.zip"]
    assert [p.name for p in tmp_path.iterdir()] == [f"{backup.PREFIX}c.zip"]

    only_old = tmp_path / "old"
    only_old.mkdir()
    p = only_old / f"{backup.PREFIX}x.zip"
    p.write_bytes(b"x")
    os.utime(p, (now - 90 * 86400, now - 90 * 86400))
    assert backup.prune(only_old, keep_days=30) == []  # never delete the last one


async def test_daily_backup_goes_to_admins(h, settings):
    await add_group(h)
    await h.create_account("boss", StaffRole.ADMIN)
    async with h.sessions() as s:
        account = await repo.get_account_by_username(s, "boss")
        await repo.upsert_user(s, h.user(55, "Boss"))
        await repo.link_telegram(s, account, 55)
        await s.commit()

    await backup.run_backup(h.bot, settings, h.sessions)
    sent = [r for r in h.tg.requests if isinstance(r, methods.SendDocument)]
    assert sorted(r.chat_id for r in sent) == [1, 55]  # ADMIN_IDS + admin account linked to Telegram
    assert "ttpu-backup-" in sent[0].caption and "BACKUP_PASSWORD" in sent[0].caption  # warns: not encrypted


async def test_admin_can_request_a_backup(h):
    admin = h.user(1, "Admin")
    await h.text(admin, "/start")
    await h.click(admin, "lang:en")
    await h.text(admin, "/backup")
    assert h.tg.last(methods.SendDocument).chat_id == 1

    student = h.user(77, "Student")
    await h.text(student, "/start")
    await h.click(student, "lang:en")
    h.tg.clear()
    await h.text(student, "/backup")  # not an admin: nothing is sent
    assert not any(isinstance(r, methods.SendDocument) for r in h.tg.requests)


def test_next_run():
    assert backup.next_run(datetime(2026, 1, 1, 2, 0), time(3, 0)) == datetime(2026, 1, 1, 3, 0)
    assert backup.next_run(datetime(2026, 1, 1, 3, 0), time(3, 0)) == datetime(2026, 1, 2, 3, 0)
