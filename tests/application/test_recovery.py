from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from research_mentor.adapters.sql.base import Base
from research_mentor.adapters.sql.models import AgentRunRow, ProjectRow, ResearchSessionRow
from research_mentor.adapters.sql.uow import SqlUnitOfWork
from research_mentor.application.recovery import RunRecovery
from research_mentor.harness.phase import SessionPhase
from research_mentor.harness.state import ResearchSession


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_recovery_only_requeues_expired_running_lease(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'recovery.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session = ResearchSession(session_id="s1", phase=SessionPhase.AWAITING_PLAN_DECISION)
    async with factory.begin() as db:
        db.add(ProjectRow(project_id="p1", title="研究", domain="AI", session_id="s1", version=1, created_at=NOW, updated_at=NOW))
        db.add(ResearchSessionRow(session_id="s1", project_id="p1", version=1, phase=session.phase.value, updated_at=NOW - timedelta(days=1), payload=session.model_dump(mode="json")))
        db.add_all([
            AgentRunRow(run_id="expired", project_id="p1", command_id="c1", agent_name="plan_loop", status="running", attempt=1, lease_owner="dead", lease_expires_at=NOW-timedelta(seconds=1), row_version=2, input_snapshot={}),
            AgentRunRow(run_id="live", project_id="p1", command_id="c2", agent_name="plan_loop", status="running", attempt=1, lease_owner="live", lease_expires_at=NOW+timedelta(seconds=1), row_version=2, input_snapshot={}),
            AgentRunRow(run_id="done", project_id="p1", command_id="c3", agent_name="plan_loop", status="succeeded", attempt=1, finished_at=NOW, row_version=3, input_snapshot={}),
        ])
    recovery = RunRecovery(lambda: SqlUnitOfWork(factory), now=lambda: NOW)
    assert await recovery.requeue_expired() == ("expired",)
    async with SqlUnitOfWork(factory) as uow:
        assert (await uow.runs.get("expired")).status == "queued"
        assert (await uow.runs.get("live")).status == "running"
        assert (await uow.runs.get("done")).status == "succeeded"
        assert (await uow.sessions.get("s1")).phase is SessionPhase.AWAITING_PLAN_DECISION
    await engine.dispose()
