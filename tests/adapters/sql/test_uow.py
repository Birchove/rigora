from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from research_mentor.adapters.sql.models import (
    AgentOutputRow,
    OutboxEventRow,
    ResearchSessionRow,
    SessionEventRow,
)
from research_mentor.adapters.sql.uow import SqlUnitOfWork
from research_mentor.harness.state import (
    SessionEvent,
    SessionEventType,
    SessionPhase,
)
from research_mentor.ports.events import OutboxEvent
from research_mentor.ports.repository import AgentOutputRecord


NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


@pytest.fixture
def session_event() -> SessionEvent:
    return SessionEvent(
        event_id="e1",
        session_id="s1",
        event_type=SessionEventType.PLAN_GENERATED,
        phase_before=SessionPhase.PLANNING,
        phase_after=SessionPhase.CHECKING_KEY_INSIGHT,
        payload={},
        occurred_at=NOW.isoformat(),
    )


@pytest.fixture
def outbox_event() -> OutboxEvent:
    return OutboxEvent(
        outbox_id="o1",
        session_event_id="e1",
        project_id="p1",
        topic="session.updated",
        payload={"session_id": "s1", "version": 2},
        created_at=NOW,
    )


@pytest.fixture
def agent_output() -> AgentOutputRecord:
    return AgentOutputRecord(
        output_id="a1",
        run_id="r1",
        project_id="p1",
        agent_name="plan_loop",
        prompt_version="v1",
        session_version=2,
        structured_payload={"response_to_user": "方案已生成"},
        created_at=NOW,
    )


async def row_count(factory, row_type) -> int:
    async with factory() as db:
        return await db.scalar(select(func.count()).select_from(row_type)) or 0


async def session_version(factory) -> int:
    async with factory() as db:
        value = await db.scalar(
            select(ResearchSessionRow.version).where(
                ResearchSessionRow.session_id == "s1"
            )
        )
        assert value is not None
        return value


@pytest.mark.asyncio
async def test_uow_rolls_back_state_and_event_on_error(
    sql_context,
    updated_session,
    session_event,
    outbox_event,
) -> None:
    with pytest.raises(RuntimeError):
        async with SqlUnitOfWork(sql_context) as uow:
            await uow.sessions.save(updated_session, expected_version=1)
            await uow.events.append(session_event)
            await uow.outbox.append(outbox_event)
            raise RuntimeError("abort")

    assert await session_version(sql_context) == 1
    assert await row_count(sql_context, SessionEventRow) == 0
    assert await row_count(sql_context, OutboxEventRow) == 0


@pytest.mark.asyncio
async def test_successful_agent_commit_is_one_transaction(
    sql_context,
    updated_session,
    session_event,
    outbox_event,
    agent_output,
) -> None:
    async with SqlUnitOfWork(sql_context) as uow:
        await uow.sessions.save(updated_session, expected_version=1)
        await uow.events.append(session_event)
        await uow.outbox.append(outbox_event)
        await uow.agent_outputs.add(agent_output)

    assert await session_version(sql_context) == 2
    assert await row_count(sql_context, SessionEventRow) == 1
    assert await row_count(sql_context, OutboxEventRow) == 1
    assert await row_count(sql_context, AgentOutputRow) == 1
