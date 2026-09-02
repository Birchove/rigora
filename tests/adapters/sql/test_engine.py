import pytest
from sqlalchemy import text

from research_mentor.adapters.sql.session import create_engine


@pytest.mark.asyncio
async def test_sqlite_engine_enables_wal_and_busy_timeout(tmp_path) -> None:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'wal.db'}")
    try:
        async with engine.connect() as connection:
            journal_mode = await connection.scalar(text("PRAGMA journal_mode"))
            busy_timeout = await connection.scalar(text("PRAGMA busy_timeout"))
    finally:
        await engine.dispose()

    assert str(journal_mode).lower() == "wal"
    assert int(busy_timeout) >= 30_000
