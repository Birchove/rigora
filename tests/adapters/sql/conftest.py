from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from research_mentor.adapters.sql.base import Base
from research_mentor.adapters.sql.models import (
    AgentRunRow,
    ProjectRow,
    ResearchSessionRow,
)
from research_mentor.harness.state import ResearchSession, SessionPhase


NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def sql_context(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'shared.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session = ResearchSession(session_id="s1", phase=SessionPhase.PLANNING)
    async with factory.begin() as db:
        db.add(
            ProjectRow(
                project_id="p1",
                title="缓存研究",
                domain="computer science",
                session_id="s1",
                version=1,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.add(
            ResearchSessionRow(
                session_id="s1",
                project_id="p1",
                version=1,
                phase=session.phase.value,
                updated_at=NOW,
                payload=session.model_dump(mode="json"),
            )
        )
        db.add(
            AgentRunRow(
                run_id="r1",
                project_id="p1",
                command_id="c1",
                agent_name="plan_loop",
                status="succeeded",
                attempt=1,
            )
        )
    yield factory
    await engine.dispose()


@pytest.fixture
def updated_session() -> ResearchSession:
    return ResearchSession(
        session_id="s1",
        phase=SessionPhase.CHECKING_KEY_INSIGHT,
    )
