from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from research_mentor.adapters.sql.base import Base
from research_mentor.adapters.sql.uow import SqlUnitOfWork
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
    command_bus: object = None
    recovery: object = _NoopRecovery()
    worker: object = _NoopWorker()


@asynccontextmanager
async def _client(monkeypatch, tmp_path):
    from research_mentor.api import app as app_module

    settings = Settings(
        model_provider="demo",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'projects.db'}",
    )
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    container = _Container(
        settings=settings,
        engine=engine,
        uow_factory=lambda: SqlUnitOfWork(factory),
    )

    async def fake_build_container(received):
        assert received is settings
        return container

    monkeypatch.setattr(app_module, "build_container", fake_build_container)
    application = app_module.create_app(settings)
    async with application.router.lifespan_context(application):
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


@pytest.mark.anyio
async def test_create_project_and_fetch_view(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path) as client:
        created = await client.post(
            "/api/v1/projects",
            json={"title": "缓存研究", "domain": "computer_science"},
        )

        assert created.status_code == 201
        assert created.json() == {
            "project_id": created.json()["project_id"],
            "title": "缓存研究",
            "domain": "computer_science",
            "version": 1,
            "phase": "awaiting_idea",
            "is_demo": False,
            "allowed_commands": [
                "submit_idea",
                "cancel_run",
                "restart_research",
                "archive_project",
            ],
            "last_event_sequence": 1,
            "active_run": None,
            "validation_candidates": [],
        }

        fetched = await client.get(
            f"/api/v1/projects/{created.json()['project_id']}"
        )
        assert fetched.status_code == 200
        assert fetched.json() == created.json()


@pytest.mark.anyio
async def test_project_list_is_stable_and_domain_alias_is_normalized(
    monkeypatch, tmp_path
):
    async with _client(monkeypatch, tmp_path) as client:
        first = await client.post(
            "/api/v1/projects", json={"title": "一", "domain": "CS"}
        )
        second = await client.post(
            "/api/v1/projects", json={"title": "二", "domain": "计算机科学"}
        )
        response = await client.get("/api/v1/projects")

        assert first.json()["domain"] == "computer_science"
        assert second.json()["domain"] == "computer_science"
        assert response.status_code == 200
        assert [item["project_id"] for item in response.json()] == [
            second.json()["project_id"],
            first.json()["project_id"],
        ]


@pytest.mark.anyio
async def test_project_errors_use_stable_envelope(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path) as client:
        unsupported = await client.post(
            "/api/v1/projects", json={"title": "研究", "domain": "biology"}
        )
        missing = await client.get("/api/v1/projects/missing")
        malformed = await client.post(
            "/api/v1/projects", json={"title": "", "domain": "computer_science"}
        )

        assert unsupported.status_code == 422
        assert unsupported.json()["error"]["code"] == "unsupported_domain"
        assert missing.status_code == 404
        assert missing.json()["error"] == {
            "code": "project_not_found",
            "message": "项目不存在。",
            "retryable": False,
            "details": {},
        }
        assert malformed.status_code == 422
        assert malformed.json()["error"]["code"] == "validation_error"
