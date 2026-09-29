"""Group names from the university's public EduPage timetable.

Only the public timetable is read (the same data https://ttpu.edupage.org/timetable/
shows to anyone); nothing about students is ever sent to EduPage.
"""

from __future__ import annotations

import logging
from datetime import date

import aiohttp

from app.services.validators import is_group_name

log = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=30)


class EdupageError(Exception):
    pass


async def _call(http: aiohttp.ClientSession, base_url: str, script: str, func: str, args: list) -> dict:
    url = f"{base_url.rstrip('/')}/timetable/server/{script}.js"
    try:
        async with http.post(url, params={"__func": func}, json={"__args": args, "__gsh": "00000000"}) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, ValueError) as e:
        raise EdupageError(f"{func}: {e}") from e
    if not isinstance(data, dict) or "r" not in data:
        raise EdupageError(f"{func}: unexpected response")
    return data["r"]


def _school_year(today: date) -> int:
    return today.year if today.month >= 8 else today.year - 1


async def fetch_group_names(base_url: str, today: date | None = None) -> list[str]:
    """Names of the groups ("classes") in the newest published timetable."""
    today = today or date.today()
    async with aiohttp.ClientSession(timeout=TIMEOUT) as http:
        viewer = await _call(http, base_url, "ttviewer", "getTTViewerData", [None, _school_year(today)])
        try:
            timetables = [t for t in viewer["regular"]["timetables"] if not t.get("hidden")]
        except (KeyError, TypeError) as e:
            raise EdupageError("no timetables in the response") from e
        if not timetables:
            raise EdupageError("no published timetable")
        # The newest timetable that has started; else the first upcoming one.
        started = [t for t in timetables if t["datefrom"] <= today.isoformat()]
        current = max(started, key=lambda t: t["datefrom"]) if started else min(timetables, key=lambda t: t["datefrom"])
        raw = await _call(http, base_url, "regulartt", "regularttGetData", [None, current["tt_num"]])
    try:
        tables = {t["id"]: t.get("data_rows", []) for t in raw["dbiAccessorRes"]["tables"]}
    except (KeyError, TypeError) as e:
        raise EdupageError("no tables in the timetable") from e
    names = {" ".join(str(c.get("name", "")).split()) for c in tables.get("classes", [])}
    valid = sorted(n for n in names if is_group_name(n))
    if skipped := sorted(n for n in names if n and not is_group_name(n)):
        log.info("Skipped EduPage classes with unusable names: %s", ", ".join(skipped))
    if not valid:
        raise EdupageError("the timetable has no groups")
    return valid
