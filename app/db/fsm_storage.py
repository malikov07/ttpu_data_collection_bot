"""aiogram FSM storage kept in the bot's own database.

Half-filled registration forms survive restarts without running Redis.
"""

from __future__ import annotations

from typing import Any, Mapping

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import FsmRecord, utcnow


def _key(key: StorageKey) -> str:
    return ":".join(
        str(part or "")
        for part in (
            key.bot_id,
            key.chat_id,
            key.user_id,
            key.thread_id,
            key.business_connection_id,
            key.destiny,
        )
    )


class DbStorage(BaseStorage):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = session_factory

    async def _upsert(self, key: StorageKey, **values: Any) -> None:
        async with self.sessions() as s:
            dialect = s.bind.dialect.name
            insert = pg_insert if dialect == "postgresql" else sqlite_insert
            values["updated_at"] = utcnow()
            stmt = insert(FsmRecord).values(key=_key(key), **values)
            stmt = stmt.on_conflict_do_update(index_elements=[FsmRecord.key], set_=values)
            await s.execute(stmt)
            await s.commit()

    async def _get(self, key: StorageKey) -> FsmRecord | None:
        async with self.sessions() as s:
            return await s.scalar(select(FsmRecord).where(FsmRecord.key == _key(key)))

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        value = state.state if isinstance(state, State) else state
        await self._upsert(key, state=value)

    async def get_state(self, key: StorageKey) -> str | None:
        record = await self._get(key)
        return record.state if record else None

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        await self._upsert(key, data=dict(data))

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        record = await self._get(key)
        return dict(record.data or {}) if record else {}

    async def close(self) -> None:
        pass
