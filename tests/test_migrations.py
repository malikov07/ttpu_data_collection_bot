"""The Alembic migrations must produce exactly the schema in app/db/models.py."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.db import create_engine, init_db
from app.db.models import Base


async def test_migrations_match_models(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'm.db'}")
    await init_db(engine)
    await init_db(engine)  # idempotent

    def diff(conn):
        return compare_metadata(MigrationContext.configure(conn), Base.metadata)

    async with engine.connect() as conn:
        assert await conn.run_sync(diff) == []
    await engine.dispose()
