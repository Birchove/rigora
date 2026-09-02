"""Async SQLAlchemy engine and session construction."""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_SQLITE_BUSY_TIMEOUT_SECONDS = 30.0
_SQLITE_BUSY_TIMEOUT_MS = 30_000


def _is_sqlite_url(database_url: str) -> bool:
    return database_url.startswith("sqlite")


def _sqlite3_connection(dbapi_connection):
    raw = dbapi_connection
    for _ in range(4):
        inner = getattr(raw, "driver_connection", None) or getattr(
            raw, "_connection", None
        )
        if inner is None or inner is raw:
            break
        raw = inner
    return raw


def _apply_sqlite_pragmas(dbapi_connection) -> None:
    raw = _sqlite3_connection(dbapi_connection)
    cursor = raw.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MS}")
    finally:
        cursor.close()


def create_engine(database_url: str) -> AsyncEngine:
    if not _is_sqlite_url(database_url):
        return create_async_engine(database_url)
    engine = create_async_engine(
        database_url,
        connect_args={"timeout": _SQLITE_BUSY_TIMEOUT_SECONDS},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_connect(dbapi_connection, _connection_record) -> None:
        _apply_sqlite_pragmas(dbapi_connection)

    return engine


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
