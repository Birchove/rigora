from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from research_mentor.adapters.sql.base import Base
from research_mentor.adapters.sql.uow import SqlUnitOfWork
from research_mentor.application.command_bus import CommandBus
from research_mentor.application.commands import (
    AgentCommandReceipt,
    DeterministicCommandResult,
)
from research_mentor.config import Settings
from research_mentor.domain.jobs import AgentRun
from research_mentor.domain.projects import ResearchProject
from research_mentor.harness.phase import SessionPhase
from research_mentor.harness.state import ResearchSession


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)
IDEA = {
    "original_idea": "研究缓存恢复策略",
    "domain": "computer science",
    "time_limit": "两周",
}


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
    command_bus: object
    recovery: object = _NoopRecovery()
    worker: object = _NoopWorker()


async def _agent_handler(command, uow, project, session):
    run = AgentRun(
        run_id=f"run-{command.command_id}",
        project_id=project.project_id,
        command_id=command.command_id,
        agent_name="idea_review",
        status="queued",
        attempt=0,
    )
    await uow.runs.add(run)
    return AgentCommandReceipt(
        project_id=project.project_id,
        command_id=command.command_id,
        run_id=run.run_id,
    )


async def _deterministic_handler(command, uow, project, session):
    updated = session.model_copy(update={"phase": SessionPhase.PLANNING})
    await uow.sessions.save(updated, expected_version=project.version - 1)
    return DeterministicCommandResult(
        project_id=project.project_id,
        command_id=command.command_id,
        session_id=session.session_id,
        version=project.version,
        phase=updated.phase,
    )


@asynccontextmanager
async def _client(monkeypatch, tmp_path):
    from research_mentor.api import app as app_module

    settings = Settings(
        model_provider="demo",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'commands-api.db'}",
    )
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    uow_factory = lambda: SqlUnitOfWork(factory)
    async with uow_factory() as uow:
        await uow.projects.add(
            ResearchProject(
                project_id="p1",
                title="缓存研究",
                domain="computer_science",
                session_id="s1",
                version=1,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await uow.sessions.add(ResearchSession(session_id="s1"), project_id="p1")
    bus = CommandBus(
        uow_factory,
        handlers={
            "submit_idea": _agent_handler,
            "archive_project": _deterministic_handler,
        },
        now=lambda: NOW,
    )
    container = _Container(settings, engine, uow_factory, bus)

    async def fake_build_container(received):
        return container

    monkeypatch.setattr(app_module, "build_container", fake_build_container)
    application = app_module.create_app(settings)
    async with application.router.lifespan_context(application):
        transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client, application


@pytest.mark.anyio
async def test_agent_and_deterministic_commands_have_distinct_responses(
    monkeypatch, tmp_path
):
    async with _client(monkeypatch, tmp_path) as (client, _):
        queued = await client.post(
            "/api/v1/projects/p1/commands",
            json={
                "type": "submit_idea",
                "project_id": "p1",
                "command_id": "agent-1",
                "expected_version": 1,
                "idea": IDEA,
            },
        )
        assert queued.status_code == 202
        assert queued.json() == {"command_id": "agent-1", "run_id": "run-agent-1"}

        # 新项目用于不受 active run 影响地验证确定性 command。
        created = await client.post(
            "/api/v1/projects",
            json={"title": "可归档", "domain": "computer_science"},
        )
        project_id = created.json()["project_id"]
        # 该 fake bus 只注册了 handler；新项目仍由同一 repository 提供 view。
        decided = await client.post(
            f"/api/v1/projects/{project_id}/commands",
            json={
                "type": "archive_project",
                "project_id": project_id,
                "command_id": "deterministic-1",
                "expected_version": 1,
            },
        )
        assert decided.status_code == 200
        assert decided.json()["project_id"] == project_id
        assert decided.json()["version"] == 2
        assert decided.json()["phase"] == "planning"


@pytest.mark.anyio
async def test_duplicate_command_preserves_original_response_type(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path) as (client, _):
        body = {
            "type": "submit_idea",
            "project_id": "p1",
            "command_id": "same",
            "expected_version": 1,
            "idea": IDEA,
        }
        first = await client.post("/api/v1/projects/p1/commands", json=body)
        duplicate = await client.post("/api/v1/projects/p1/commands", json=body)

        assert first.status_code == duplicate.status_code == 202
        assert first.json() == duplicate.json()


@pytest.mark.anyio
async def test_command_conflicts_and_validation_use_stable_errors(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path) as (client, _):
        stale = await client.post(
            "/api/v1/projects/p1/commands",
            json={
                "type": "submit_idea",
                "project_id": "p1",
                "command_id": "stale",
                "expected_version": 99,
                "idea": IDEA,
            },
        )
        mismatch = await client.post(
            "/api/v1/projects/p1/commands",
            json={
                "type": "submit_idea",
                "project_id": "other",
                "command_id": "wrong-project",
                "expected_version": 1,
                "idea": IDEA,
            },
        )
        unknown = await client.post(
            "/api/v1/projects/p1/commands",
            json={"type": "unknown", "project_id": "p1"},
        )

        assert stale.status_code == 409
        assert stale.json()["error"] == {
            "code": "stale_project_version",
            "message": "项目已在其他操作中更新，请刷新后重试。",
            "retryable": False,
            "details": {},
        }
        assert mismatch.status_code == 422
        assert mismatch.json()["error"]["code"] == "project_id_mismatch"
        assert unknown.status_code == 422
        assert unknown.json()["error"]["code"] == "validation_error"


@pytest.mark.anyio
async def test_openapi_exposes_command_discriminator_success_and_errors(
    monkeypatch, tmp_path
):
    async with _client(monkeypatch, tmp_path) as (_, application):
        schema = application.openapi()
        paths = schema["paths"]
        assert {
            "/api/v1/projects",
            "/api/v1/projects/{project_id}",
            "/api/v1/projects/{project_id}/commands",
            "/api/v1/health",
        } == set(paths)
        operation = paths["/api/v1/projects/{project_id}/commands"]["post"]
        body_schema = operation["requestBody"]["content"]["application/json"]["schema"]
        assert body_schema["discriminator"]["propertyName"] == "type"
        assert len(body_schema["oneOf"]) == 15
        assert {"200", "202", "404", "409", "422", "503"} <= set(
            operation["responses"]
        )
