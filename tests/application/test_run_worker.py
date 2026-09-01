import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from research_mentor.adapters.model.errors import ModelTemporarilyUnavailable
from research_mentor.adapters.sql.base import Base
from research_mentor.adapters.sql.models import (
    AgentRunRow,
    OutboxEventRow,
    ProjectRow,
    ResearchSessionRow,
    SessionEventRow,
)
from research_mentor.adapters.sql.uow import SqlUnitOfWork
from research_mentor.application.command_bus import CommandBus
from research_mentor.application.commands import CancelRunCommand
from research_mentor.application.handlers import CancelRunHandler
from research_mentor.application.run_worker import AgentRunWorker, RunService
from research_mentor.domain.jobs import AgentRun
from research_mentor.errors import ModelOutputInvalid
from research_mentor.harness.phase import SessionPhase
from research_mentor.harness.state import ResearchSession


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def run_context(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'runs.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session = ResearchSession(session_id="s1", phase=SessionPhase.WORKING)
    async with factory.begin() as db:
        db.add(ProjectRow(project_id="p1", title="研究", domain="AI", session_id="s1", version=1, created_at=NOW, updated_at=NOW))
        db.add(ResearchSessionRow(session_id="s1", project_id="p1", version=1, phase=session.phase.value, updated_at=NOW, payload=session.model_dump(mode="json")))
    yield factory
    await engine.dispose()


async def seed(factory, *, run_id="r1", status="queued", **values):
    run = AgentRun(run_id=run_id, project_id="p1", command_id=f"c-{run_id}", agent_name="working_qa", status=status, attempt=values.pop("attempt", 0), input_snapshot={"message_ids": ["m1"], "question": "原问题"}, **values)
    async with SqlUnitOfWork(factory) as uow:
        await uow.runs.add(run)


@pytest.mark.anyio
async def test_worker_retries_transient_failure_without_sleeping_in_request(run_context):
    await seed(run_context)
    calls = 0

    async def handler(run, snapshot, repair_errors):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ModelTemporarilyUnavailable("429")
        return {"ok": True}

    clock = [NOW]
    worker = AgentRunWorker(lambda: SqlUnitOfWork(run_context), handlers={"working_qa": handler}, worker_id="w1", retry_limit=3, now=lambda: clock[0])
    assert await worker.drain_once() == "r1"
    async with SqlUnitOfWork(run_context) as uow:
        retry = await uow.runs.get("r1")
    assert retry.status == "queued" and retry.attempt == 1
    assert retry.available_at == NOW + timedelta(seconds=2)
    assert await worker.drain_once() is None
    clock[0] = retry.available_at
    assert await worker.drain_once() == "r1"
    async with SqlUnitOfWork(run_context) as uow:
        completed = await uow.runs.get("r1")
    assert completed.status == "succeeded" and completed.attempt == 2


@pytest.mark.anyio
async def test_schema_failure_allows_only_two_minimal_repair_requests(run_context):
    await seed(run_context)
    repair_inputs = []

    async def handler(run, snapshot, repair_errors):
        repair_inputs.append(repair_errors)
        if len(repair_inputs) < 3:
            raise ModelOutputInvalid(errors=[{"loc": ("answer",), "msg": "required", "input": "secret raw payload"}])
        return {"ok": True}

    worker = AgentRunWorker(lambda: SqlUnitOfWork(run_context), handlers={"working_qa": handler}, worker_id="w1", now=lambda: NOW)
    await worker.drain_once()
    assert len(repair_inputs) == 3
    assert repair_inputs[0] is None
    assert repair_inputs[1] == [{"loc": ["answer"], "msg": "required"}]
    assert "secret" not in str(repair_inputs)


@pytest.mark.anyio
async def test_cancel_unlocks_only_after_worker_confirms(run_context):
    await seed(run_context)
    service = RunService(lambda: SqlUnitOfWork(run_context), now=lambda: NOW)
    assert await service.request_cancel("r1") is True
    assert await service.has_active_run("p1") is True
    worker = AgentRunWorker(lambda: SqlUnitOfWork(run_context), handlers={}, worker_id="w1", now=lambda: NOW)
    assert await worker.confirm_cancelled("r1") is True
    assert await service.has_active_run("p1") is False


@pytest.mark.anyio
async def test_cancel_command_requests_cooperative_cancel_before_worker_unlocks(
    run_context,
):
    await seed(run_context)
    bus = CommandBus(
        lambda: SqlUnitOfWork(run_context),
        handlers={"cancel_run": CancelRunHandler()},
        now=lambda: NOW,
    )
    result = await bus.dispatch(
        CancelRunCommand(
            project_id="p1",
            command_id="cancel-r1",
            expected_version=1,
            run_id="r1",
        )
    )
    service = RunService(lambda: SqlUnitOfWork(run_context), now=lambda: NOW)
    assert result.payload == {"run_id": "r1", "cancel_requested": True}
    assert await service.has_active_run("p1") is True

    worker = AgentRunWorker(
        lambda: SqlUnitOfWork(run_context), handlers={}, worker_id="w1", now=lambda: NOW
    )
    assert await worker.confirm_cancelled("r1") is True
    assert await service.has_active_run("p1") is False


@pytest.mark.anyio
async def test_two_workers_compete_and_cas_completes_once(run_context):
    await seed(run_context)
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def handler(run, snapshot, repair_errors):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return {"ok": True}

    w1 = AgentRunWorker(lambda: SqlUnitOfWork(run_context), handlers={"working_qa": handler}, worker_id="w1", lease_seconds=10, now=lambda: NOW)
    w2 = AgentRunWorker(lambda: SqlUnitOfWork(run_context), handlers={"working_qa": handler}, worker_id="w2", lease_seconds=10, now=lambda: NOW)
    task = asyncio.create_task(w1.drain_once())
    await started.wait()
    assert await w2.drain_once() is None
    assert await w2.claim("r1") is False
    assert await w1.renew_lease("r1") is True
    release.set()
    await task
    assert calls == 1
    async with SqlUnitOfWork(run_context) as uow:
        stored = await uow.runs.get("r1")
    assert stored.status == "succeeded" and stored.row_version >= 3


@pytest.mark.anyio
async def test_running_agent_uses_frozen_input_snapshot(run_context):
    await seed(run_context)
    received = []

    async def handler(run, snapshot, repair_errors):
        received.append(snapshot)
        snapshot["message_ids"].append("mutated")
        return {}

    worker = AgentRunWorker(lambda: SqlUnitOfWork(run_context), handlers={"working_qa": handler}, worker_id="w1", now=lambda: NOW)
    await worker.drain_once()
    assert received[0]["message_ids"] == ["m1", "mutated"]
    async with SqlUnitOfWork(run_context) as uow:
        stored = await uow.runs.get("r1")
    assert stored.input_snapshot["message_ids"] == ["m1"]


@pytest.mark.anyio
async def test_timeout_and_final_failure_preserve_business_phase(run_context):
    await seed(run_context, run_id="timeout")

    async def slow(*args):
        await asyncio.sleep(1)

    worker = AgentRunWorker(lambda: SqlUnitOfWork(run_context), handlers={"working_qa": slow}, worker_id="w1", run_timeout=0.01, now=lambda: NOW)
    await worker.drain_once()
    async with SqlUnitOfWork(run_context) as uow:
        run = await uow.runs.get("timeout")
        session = await uow.sessions.get("s1")
    async with run_context() as db:
        event_count = await db.scalar(select(func.count()).select_from(SessionEventRow))
        outbox_count = await db.scalar(select(func.count()).select_from(OutboxEventRow))
        event = await db.scalar(select(SessionEventRow))
    assert run.status == "timed_out" and run.finished_at == NOW
    assert run.error_code == "run_timeout" and run.public_message
    assert session.phase is SessionPhase.WORKING
    assert event_count == outbox_count == 1
    assert event.event_type == "run_failed"
    assert event.phase_before == event.phase_after == SessionPhase.WORKING.value
