from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from research_mentor.adapters.sql.base import Base
from research_mentor.adapters.sql.uow import SqlUnitOfWork
from research_mentor.application.event_stream import (
    PUBLIC_EVENT_TYPES,
    EventStreamService,
    PersistedPublicEvent,
)
from research_mentor.api.events import _cursor
from research_mentor.config import Settings


class _NoopRecovery:
    async def requeue_expired(self):
        return ()


class _NoopWorker:
    async def start(self):
        return None

    async def stop(self):
        return None


@dataclass
class _Container:
    settings: Settings
    engine: object
    uow_factory: object
    recovery: object = _NoopRecovery()
    worker: object = _NoopWorker()


@asynccontextmanager
async def _client(monkeypatch, tmp_path):
    from research_mentor.api import app as app_module

    settings = Settings(
        model_provider="demo",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'events.db'}",
    )
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    container = _Container(settings, engine, lambda: SqlUnitOfWork(factory))

    async def fake_build_container(received):
        assert received is settings
        return container

    monkeypatch.setattr(app_module, "build_container", fake_build_container)
    app = app_module.create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            yield client


def test_public_event_types_are_exactly_whitelisted():
    assert PUBLIC_EVENT_TYPES == {
        "command.accepted",
        "run.started",
        "run.completed",
        "run.failed",
        "retrieval.started",
        "retrieval.results",
        "retrieval.unavailable",
        "document.parsing_progress",
        "agent.stage",
        "session.phase_changed",
        "evidence.added",
        "user_input.required",
        "export.ready",
    }


def test_cursor_uses_larger_header_or_query():
    assert _cursor(7, "3") == 7
    assert _cursor(3, "7") == 7


@pytest.mark.anyio
async def test_cursor_validation_is_stable_and_uses_larger_header_or_query(
    monkeypatch, tmp_path
):
    async with _client(monkeypatch, tmp_path) as client:
        invalid = await client.get(
            "/api/v1/projects/p1/events", headers={"Last-Event-ID": "bad"}
        )
        negative = await client.get("/api/v1/projects/p1/events?after=-1")

    assert invalid.status_code == negative.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"


class _EventRepository:
    def __init__(self, batches):
        self.batches = list(batches)
        self.cursors = []

    async def list_for_project_after(self, project_id, *, after):
        self.cursors.append((project_id, after))
        return self.batches.pop(0) if self.batches else []


class _Projects:
    async def get(self, project_id):
        return object() if project_id == "p1" else None


class _Uow:
    def __init__(self, events):
        self.events = events
        self.projects = _Projects()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


def _event(sequence, event_type="run.failed", payload=None):
    return PersistedPublicEvent(
        project_id="p1",
        sequence=sequence,
        event_type=event_type,
        phase_before="working",
        phase_after="working",
        payload=payload or {
            "run_id": "r1",
            "status": "timed_out",
            "public_message": "请重试",
        },
        occurred_at=datetime.now(timezone.utc),
    )


@pytest.mark.anyio
async def test_replay_is_increasing_unique_and_payload_is_filtered():
    repository = _EventRepository(
        [[
            _event(3),
            _event(
                2,
                payload={
                    "run_id": "r2",
                    "system_prompt": "x",
                    "public_message": {"ok": "safe", "apiKey": "hidden"},
                },
            ),
            _event(3),
        ]]
    )
    service = EventStreamService(
        lambda: _Uow(repository), poll_interval=0.001, heartbeat_interval=1
    )

    chunks = [chunk async for chunk in service.stream("p1", after=1, max_cycles=1)]

    assert [chunk.splitlines()[0] for chunk in chunks] == ["id: 2", "id: 3"]
    assert "system_prompt" not in "".join(chunks)
    assert "apiKey" not in "".join(chunks)
    assert repository.cursors == [("p1", 1)]


@pytest.mark.anyio
async def test_unknown_event_is_not_public_and_heartbeat_is_not_persisted():
    repository = _EventRepository(
        [[_event(1, event_type="internal.trace", payload={"secret": "x"})], []]
    )
    ticks = iter([0.0, 16.0, 16.0])
    service = EventStreamService(
        lambda: _Uow(repository),
        poll_interval=0.001,
        heartbeat_interval=15,
        monotonic=lambda: next(ticks),
        sleep=lambda _: _instant_sleep(),
    )

    chunks = [chunk async for chunk in service.stream("p1", after=0, max_cycles=2)]

    assert chunks == [": heartbeat\n\n"]
    assert repository.cursors == [("p1", 0), ("p1", 1)]


async def _instant_sleep():
    return None
