import asyncio
from dataclasses import dataclass

import httpx
import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from research_mentor.adapters.sql.base import Base
from research_mentor.application.run_worker import AgentRunWorker
from research_mentor.config import Settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeRecovery:
    def __init__(self, calls, *, error=None):
        self.calls = calls
        self.error = error

    async def requeue_expired(self):
        self.calls.append("recovery")
        if self.error is not None:
            raise self.error


class FakeWorker:
    def __init__(self, calls, *, start_error=None):
        self.calls = calls
        self.start_error = start_error

    async def start(self):
        self.calls.append("worker.start")
        if self.start_error is not None:
            raise self.start_error

    async def stop(self):
        self.calls.append("worker.stop")


class FakeEngine:
    def __init__(self, calls):
        self.calls = calls

    async def dispose(self):
        self.calls.append("engine.dispose")


@dataclass
class FakeContainer:
    settings: Settings
    recovery: FakeRecovery
    worker: FakeWorker
    engine: FakeEngine


@pytest.mark.anyio
async def test_health_uses_injected_settings_and_lifecycle_order(monkeypatch, tmp_path):
    from research_mentor.api import app as app_module

    settings = Settings(
        model_provider="demo",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'health.db'}",
    )
    calls = []
    container = FakeContainer(
        settings=settings,
        recovery=FakeRecovery(calls),
        worker=FakeWorker(calls),
        engine=FakeEngine(calls),
    )

    async def fake_build_container(received):
        assert received is settings
        calls.append("build")
        return container

    monkeypatch.setattr(app_module, "build_container", fake_build_container)
    application = app_module.create_app(settings)

    assert application.title == "Rigora API"
    assert application.version == "1.0.0"
    assert application.state.settings is settings
    async with application.router.lifespan_context(application):
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "database": "ok",
            "model_provider": "demo",
        }

    assert calls == [
        "build",
        "recovery",
        "worker.start",
        "worker.stop",
        "engine.dispose",
    ]


@pytest.mark.anyio
@pytest.mark.parametrize("failure_at", ["recovery", "worker.start"])
async def test_startup_failure_disposes_created_resources(
    monkeypatch, tmp_path, failure_at
):
    from research_mentor.api import app as app_module

    settings = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'failed.db'}")
    calls = []
    container = FakeContainer(
        settings=settings,
        recovery=FakeRecovery(
            calls, error=RuntimeError("recovery failed") if failure_at == "recovery" else None
        ),
        worker=FakeWorker(
            calls,
            start_error=(
                RuntimeError("worker failed") if failure_at == "worker.start" else None
            ),
        ),
        engine=FakeEngine(calls),
    )

    async def fake_build_container(received):
        return container

    monkeypatch.setattr(app_module, "build_container", fake_build_container)
    application = app_module.create_app(settings)

    with pytest.raises(RuntimeError):
        async with application.router.lifespan_context(application):
            pass

    if failure_at == "recovery":
        assert calls == ["recovery", "engine.dispose"]
    else:
        assert calls == [
            "recovery",
            "worker.start",
            "worker.stop",
            "engine.dispose",
        ]


@pytest.mark.anyio
async def test_worker_start_and_stop_cancel_background_polling():
    entered = asyncio.Event()
    blocked = asyncio.Event()

    async def drain_once():
        entered.set()
        await blocked.wait()

    worker = AgentRunWorker(
        lambda: None,
        handlers={},
        worker_id="lifecycle-test",
        poll_interval=0.001,
    )
    worker.drain_once = drain_once

    await worker.start()
    await entered.wait()
    await worker.stop()

    assert worker.is_running is False


@pytest.mark.anyio
async def test_real_demo_container_starts_with_migrated_sqlite(tmp_path):
    from research_mentor.api.app import create_app

    database_url = f"sqlite+aiosqlite:///{tmp_path / 'demo.db'}"
    migration_engine = create_async_engine(database_url)
    async with migration_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await migration_engine.dispose()

    settings = Settings(model_provider="demo", database_url=database_url)
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        assert application.state.container.settings is settings
        assert application.state.container.worker.is_running is True
    assert application.state.container.worker.is_running is False
