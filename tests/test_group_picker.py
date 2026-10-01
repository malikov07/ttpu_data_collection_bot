"""Choosing a group among many: program first (IT, SE…), then the group."""

from __future__ import annotations

from aiogram.fsm.storage.base import StorageKey

from app import keyboards as kb
from app.callbacks import AdminCb, StaffCb
from app.db import repo
from app.db.models import StaffRole
from tests.conftest import passport_result
from tests.test_flows import ADMIN, setup_groups, start_registration, student

GROUPS = "IT1-24, IT1-26, IT2-26, IT1-25, SE1-26, SE2-25, SE-23, CYB1-26, CYB2-26, MSc_MBA-26, MSc_TE-25, AD-23, AD1-26, BM1-26, BM2-26"


async def seed(h, names: str = GROUPS):
    """Groups as the EduPage import adds them (EduPage's own spelling)."""
    admin = await setup_groups(h, "SE-23")
    async with h.sessions() as db:
        await repo.add_groups(db, [n.strip() for n in names.split(",")])
        await db.commit()
    return admin


async def chosen_group(h, uid: int) -> str | None:
    key = StorageKey(bot_id=h.bot.id, chat_id=uid, user_id=uid)
    return (await h.dp.fsm.storage.get_data(key=key)).get("group_name")


def labels(h) -> list[str]:
    return [text for text, _ in h.buttons()]


def test_program_and_order():
    assert [kb.program_of(n) for n in ("IT1-26", "MSc_MBA-26", "AKITA-24", "SE-23")] == ["IT", "MSc", "AKITA", "SE"]
    names = ["IT1-24", "IT2-26", "IT1-25", "IT1-26", "SE-24-02", "SE-24-01"]
    assert sorted(names, key=kb.group_sort_key) == ["IT1-26", "IT2-26", "IT1-25", "IT1-24", "SE-24-01", "SE-24-02"]


async def test_student_picks_program_then_group(h):
    await seed(h)
    h.vision.documents["p"] = passport_result()
    u = await start_registration(h, 100)
    await h.photo(u, "p")
    await h.click(u, "reg:correct")
    await h.contact(u, "998901234567")

    assert labels(h) == ["AD", "BM", "CYB", "IT", "MSc", "SE"]
    await h.click(u, h.button("IT"))
    assert labels(h) == ["IT1-26", "IT2-26", "IT1-25", "IT1-24", "‹ Programs"]
    await h.click(u, h.button("Programs"))  # changed their mind
    await h.click(u, h.button("MSc"))
    assert labels(h) == ["MSc_MBA-26", "MSc_TE-25", "‹ Programs"]
    await h.click(u, h.button("MSc_TE-25"))
    assert await chosen_group(h, 100) == "MSc_TE-25"


async def test_typing_the_group_still_works(h):
    await seed(h)
    h.vision.documents["p"] = passport_result()
    u = await start_registration(h, 101)
    await h.photo(u, "p")
    await h.click(u, "reg:correct")
    await h.contact(u, "998901234567")
    await h.text(u, "it1 25")
    assert await chosen_group(h, 101) == "IT1-25"


async def test_few_groups_need_no_program_step(h):
    await seed(h, "SE-24-01, SE-24-02, IT1-25")
    h.vision.documents["p"] = passport_result()
    u = await start_registration(h, 102)
    await h.photo(u, "p")
    await h.click(u, "reg:correct")
    await h.contact(u, "998901234567")
    assert labels(h) == ["IT1-25", "SE-24-01", "SE-24-02", "SE-23"]  # 4 groups: one screen, newest first


async def test_admin_lists_and_leader_pick_are_grouped(h):
    admin = await seed(h)
    await h.click(admin, AdminCb(action="groups").pack())
    assert labels(h)[:6] == ["AD", "BM", "CYB", "IT", "MSc", "SE"] and "➕ Add groups" in labels(h)
    await h.click(admin, h.button("CYB"))
    assert labels(h)[:3] == ["CYB1-26", "CYB2-26", "‹ Programs"]
    await h.click(admin, h.button("CYB2-26"))
    assert h.button("Back") == AdminCb(action="groups", value="CYB").pack()  # back to the same program

    await h.click(admin, AdminCb(action="new").pack())
    await h.text(admin, "leader.cyb")
    await h.text(admin, "Aziz Karimov")
    await h.click(admin, AdminCb(action="role", value="leader").pack())
    await h.click(admin, h.button("CYB"))
    await h.click(admin, h.button("CYB1-26"))
    assert "leader.cyb" in h.tg.texts(ADMIN)[-1]


async def test_tutor_browses_by_program_and_moves_a_student(h):
    await seed(h)
    h.vision.documents["p"] = passport_result()
    u = await start_registration(h, 103)
    await h.photo(u, "p")
    await h.click(u, "reg:correct")
    await h.contact(u, "998901234567")
    await h.text(u, "IT1-25")
    await h.photo(u, "face", size=(600, 800))
    await h.document(u, "cv.pdf", "application/pdf")
    await h.click(u, "reg:certs_done")  # no certificates
    await h.click(u, "reg:submit")

    await h.create_account("tutor", StaffRole.TUTOR)
    tutor = h.user(700, "Tutor")
    await h.text(tutor, "/start")
    await h.click(tutor, "lang:en")
    await h.text(tutor, "/login")
    await h.text(tutor, "tutor")
    await h.text(tutor, "Secret123")
    await h.text(tutor, "/students")
    assert labels(h) == ["AD", "BM", "CYB", "IT", "MSc", "SE"]
    await h.click(tutor, h.button("IT"))
    assert "IT1-25 · 1" in labels(h)
    await h.click(tutor, h.button("IT1-25 · 1"))
    assert h.button("Back") == StaffCb(action="groups", value="IT").pack()

    s = await student(h, 103)
    await h.click(tutor, StaffCb(action="efield", student_id=s.id, value="group").pack())
    await h.click(tutor, h.button("SE"))
    await h.click(tutor, h.button("SE1-26"))
    assert (await student(h, 103)).group.name == "SE1-26"
