"""Backups: encrypted archive of the database and uploads, pruning, sending."""

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
from app.db.models import StaffRole
from app.services import backup


async def add_group(h, name="SE-24-01"):
    async with h.sessions() as s:
        await repo.add_groups(s, [name])
        await s.commit()


async def test_backup_is_an_encrypted_archive_of_database_and_uploads(h, settings, tmp_path):
    await add_group(h)
    (settings.uploads_dir / "3").mkdir(parents=True)
    (settings.uploads_dir / "3" / "cv.pdf").write_bytes(b"%PDF-1.4 test")
    settings = settings.model_copy(update={"backup_password": SecretStr("S3cret-backup")})

    b = await backup.create_backup(settings, h.sessions)
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
