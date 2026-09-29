"""Alembic environment.

Used both from the app (``init_db`` passes an open connection) and from the
CLI (``alembic revision --autogenerate``), which builds its own engine.
"""

from __future__ import annotations

import asyncio

from alembic import context

from app.db.models import Base

config = context.config
target_metadata = Base.metadata


def run_with(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite needs table rebuilds for ALTERs
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_cli() -> None:
    from app.config import get_settings
    from app.db import create_engine

    engine = create_engine(get_settings().database_url)
    async with engine.begin() as conn:
        await conn.run_sync(run_with)
    await engine.dispose()


connection = config.attributes.get("connection")
if connection is not None:
    run_with(connection)
else:
    asyncio.run(_run_cli())
