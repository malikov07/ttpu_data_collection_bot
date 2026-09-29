"""Importing groups from the public EduPage timetable (EduPage itself is faked)."""

from __future__ import annotations

from datetime import date

import pytest

from app.callbacks import AdminCb
from app.db import repo
from app.db.models import StaffRole
from app.services import edupage
from tests.test_flows import ADMIN, setup_groups
from tests.test_web import admin_client

VIEWER = {
    "regular": {
        "timetables": [
            {"tt_num": "455", "datefrom": "2026-09-06", "hidden": False},
            {"tt_num": "460", "datefrom": "2026-09-27", "hidden": False},
            {"tt_num": "461", "datefrom": "2026-10-04", "hidden": False},  # not started yet
            {"tt_num": "999", "datefrom": "2026-09-28", "hidden": True},  # draft
        ]
    }
}


def timetable(names: list[str]) -> dict:
    classes = [{"id": f"*{i}", "name": n} for i, n in enumerate(names)]
    return {"dbiAccessorRes": {"tables": [{"id": "classes", "data_rows": classes}, {"id": "teachers", "data_rows": []}]}}


@pytest.fixture
def fake_edupage(monkeypatch):
    calls: list[tuple[str, list]] = []
    state = {"names": ["SE-24-01", "IT1-26", "MSc_MBA-26", "  CYB1-26 ", "Bad name!", ""], "fail": False}

    async def fake_call(http, base_url, script, func, args):
        calls.append((func, args))
        if state["fail"]:
            raise edupage.EdupageError("down")
        return VIEWER if func == "getTTViewerData" else timetable(state["names"])

    monkeypatch.setattr(edupage, "_call", fake_call)
    state["calls"] = calls
    return state


async def test_fetch_uses_the_current_timetable_and_skips_bad_names(fake_edupage):
    names = await edupage.fetch_group_names("https://ttpu.edupage.org", today=date(2026, 9, 30))
    assert names == ["CYB1-26", "IT1-26", "MSc_MBA-26", "SE-24-01"]
    assert fake_edupage["calls"] == [("getTTViewerData", [None, 2026]), ("regularttGetData", [None, "460"])]


async def test_fetch_fails_cleanly(fake_edupage):
    fake_edupage["names"] = ["Bad name!"]
    with pytest.raises(edupage.EdupageError):
        await edupage.fetch_group_names("https://ttpu.edupage.org", today=date(2026, 9, 30))


async def test_admin_imports_groups_on_the_website(web, h, fake_edupage):
    await setup_groups(h, "SE-24-01, OLD-20")  # OLD-20 graduated: not on EduPage any more
    c = await admin_client(web, h)
    r = await c.post("/api/groups/import")
    assert r.status_code == 200, r.text
    assert r.json() == {"added": ["CYB1-26", "IT1-26", "MSc_MBA-26"], "existing": ["SE-24-01"], "missing": ["OLD-20"]}
    names = [g["name"] for g in (await c.get("/api/groups")).json()]
    assert names == ["CYB1-26", "IT1-26", "MSc_MBA-26", "OLD-20", "SE-24-01"]  # nothing removed; EduPage spelling kept

    r = await c.post("/api/groups/import")  # running it again changes nothing
    assert r.json()["added"] == []

    fake_edupage["fail"] = True
    r = await c.post("/api/groups/import")
    assert r.status_code == 502 and r.json()["detail"] == "edupage_unavailable"


async def test_only_admins_can_import(web, h, fake_edupage):
    await setup_groups(h)
    await h.create_account("tutor", StaffRole.TUTOR)
    c, _ = await web.login("tutor")
    assert (await c.post("/api/groups/import")).status_code == 403
    assert fake_edupage["calls"] == []


async def test_admin_imports_groups_in_the_bot(h, fake_edupage):
    admin = await setup_groups(h, "SE-24-01")
    await h.click(admin, AdminCb(action="groups").pack())
    assert h.button("EduPage") == AdminCb(action="edupage").pack()
    await h.click(admin, AdminCb(action="edupage").pack())
    report = h.tg.texts(ADMIN)[-1]
    assert "4 groups" in report and "CYB1-26, IT1-26, MSc_MBA-26" in report and "Already here: 1" in report
    async with h.sessions() as s:
        assert len(await repo.list_groups(s)) == 4
