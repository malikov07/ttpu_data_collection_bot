from __future__ import annotations

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine



def create_engine(database_url: str) -> AsyncEngine:
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)

    connect_args = {"timeout": 30} if url.get_backend_name() == "sqlite" else {}
    engine = create_async_engine(database_url, pool_pre_ping=True, connect_args=connect_args)

    if url.get_backend_name() == "sqlite":

        @event.listens_for(engine.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def alembic_config():
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    return cfg


def _upgrade(connection) -> None:
    from alembic import command

    cfg = alembic_config()
    cfg.attributes["connection"] = connection
    command.upgrade(cfg, "head")


async def init_db(engine: AsyncEngine) -> None:
    """Bring the schema up to date (runs pending Alembic migrations)."""
    sqlite = engine.dialect.name == "sqlite"
    async with engine.connect() as conn:
        if sqlite:
            # SQLite rebuilds tables for ALTERs; FK checks must be off meanwhile.
            # Must run before the migration transaction starts to take effect.
            await conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        await conn.run_sync(_upgrade)
        await conn.commit()
        if sqlite:
            await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
