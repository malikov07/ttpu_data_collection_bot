"""Runtime settings that admins change on the website (stored in the DB).

Environment variables provide the defaults; saved values override them.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import repo

KV_PREFS = "prefs"


class Prefs(BaseModel):
    registration_open: bool = True
    notify_leaders: bool = True
    max_document_pages: int = Field(5, ge=1, le=10)
    min_student_age: int = Field(14, ge=10, le=100)
    max_student_age: int = Field(70, ge=10, le=100)

    @model_validator(mode="after")
    def _ages(self) -> Prefs:
        if self.min_student_age >= self.max_student_age:
            raise ValueError("min_student_age must be less than max_student_age")
        return self


def defaults(settings: Settings) -> Prefs:
    return Prefs(
        notify_leaders=settings.notify_leaders,
        max_document_pages=settings.max_document_pages,
        min_student_age=settings.min_student_age,
        max_student_age=settings.max_student_age,
    )


async def load_prefs(session: AsyncSession, settings: Settings) -> Prefs:
    base = defaults(settings).model_dump()
    raw = await repo.kv_get(session, KV_PREFS)
    if raw:
        try:
            base.update({k: v for k, v in json.loads(raw).items() if k in base})
        except (ValueError, AttributeError):
            pass
    try:
        return Prefs(**base)
    except ValueError:
        return defaults(settings)


async def save_prefs(session: AsyncSession, prefs: Prefs) -> None:
    await repo.kv_set(session, KV_PREFS, prefs.model_dump_json())
