import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from research_mentor.application.command_bus import CommandBus
from research_mentor.application.commands import (
    AgentCommandReceipt,
    Command,
    DeterministicCommandResult,
    RestartResearchCommand,
    RunCheckCommand,
    RunPlanCommand,
    SubmitRefinementCommand,
    SubmitIdeaCommand,
    command_type_names,
)
from research_mentor.application.handlers import RestartResearchHandler
from research_mentor.adapters.sql.base import Base
from research_mentor.adapters.sql.models import (
    AgentRunRow,
    OutboxEventRow,
    ProcessedCommandRow,
    ProjectRow,
    ResearchSessionRow,
    SessionEventRow,
)
from research_mentor.adapters.sql.uow import SqlUnitOfWork
from research_mentor.domain.jobs import AgentRun
from research_mentor.domain.projects import ResearchProject
from research_mentor.domain.research import InitialInput
from research_mentor.errors import (
    ConcurrencyConflict,
    IllegalTransitionError,
    InvariantViolationError,
)
from research_mentor.harness.phase import SessionPhase
from research_mentor.harness.state import (
    ResearchSession,
    SessionEvent,
    SessionEventType,
)
from research_mentor.ports.events import OutboxEvent
from research_mentor.ports.repository import ProcessedCommand


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)
INITIAL_INPUT = InitialInput(original_idea="验证压缩是否降低状态漂移", domain="AI")


class CopyRepository:
    def __init__(self, values, key):
        self.values = values
        self.key = key
        self.add_calls = 0

    async def get(self, item_id):
        value = self.values.get(item_id)
        return value.model_copy(deep=True) if value is not None else None

    async def add(self, value, **kwargs):
        self.add_calls += 1
        self.values[self.key(value)] = value.model_copy(deep=True)

    async def append(self, value):
        await self.add(value)

    async def save(self, value, *, expected_version):
        if self.values[self.key(value)].version != expected_version:
            raise ConcurrencyConflict(self.key(value), expected_version)
        self.values[self.key(value)] = value.model_copy(deep=True)

    async def find_active_for_project(self, project_id):
        return next(
            (
                value.model_copy(deep=True)
                for value in self.values.values()
                if getattr(value, "project_id", None) == project_id
                and getattr(value, "status", None) in {"queued", "running"}
            ),
            None,
        )


class ProcessedRepository:
    def __init__(self, values):
        self.values = values

    async def find(self, project_id, command_id):
        value = self.values.get((project_id, command_id))
        return value.model_copy(deep=True) if value is not None else None

    async def add(self, value):
        self.values[(value.project_id, value.command_id)] = value.model_copy(deep=True)


class FakeUow:
    def __init__(self, state):
        self.state = state

    async def __aenter__(self):
        self.projects = CopyRepository(self.state.projects, lambda item: item.project_id)
        self.sessions = CopyRepository(self.state.sessions, lambda item: item.session_id)
        self.runs = CopyRepository(self.state.runs, lambda item: item.run_id)
        self.processed_commands = ProcessedRepository(self.state.processed)
        self.events = CopyRepository(self.state.events, lambda item: item.event_id)
        self.outbox = CopyRepository(self.state.outbox, lambda item: item.outbox_id)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


@pytest.fixture
def state():
    return SimpleNamespace(
        projects={
            "p1": ResearchProject(
                project_id="p1",
                title="研究",
                domain="AI",
                session_id="s1",
                version=1,
                created_at=NOW,
                updated_at=NOW,
            )
        },
        sessions={"s1": ResearchSession(session_id="s1")},
        runs={},
        processed={},
        events={},
        outbox={},
    )


def test_command_union_names_are_exact() -> None:
    assert command_type_names() == {
        "submit_idea",
        "submit_refinement",
        "run_plan",
        "run_check",
        "decide_plan",
        "send_working_message",
        "resume_working",
        "finish_working",
        "record_main_result",
        "record_validation_result",
        "run_complete",
        "select_validations",
        "decide_plan_revision",
        "cancel_run",
        "restart_research",
        "archive_project",
    }


def test_commands_require_positive_expected_version_and_parse_by_discriminator() -> None:
    with pytest.raises(ValidationError):
        SubmitIdeaCommand(
            project_id="p1", command_id="c1", idea=INITIAL_INPUT
        )
    with pytest.raises(ValidationError):
        RunPlanCommand(
            project_id="p1", command_id="c1", expected_version=0
        )

    parsed = TypeAdapter(Command).validate_python(
        {
            "type": "run_check",
            "project_id": "p1",
            "command_id": "c2",
            "expected_version": 1,
        }
    )

    assert isinstance(parsed, RunCheckCommand)
    assert parsed.candidate_id is None
    assert RunPlanCommand(
        project_id="p1", command_id="c3", expected_version=1
    ).mode == "low"
    refinement = SubmitRefinementCommand(
        project_id="p1",
        command_id="c4",
        expected_version=1,
        refinement="限定为数据库缓存一致性",
    )
    assert refinement.refinement == "限定为数据库缓存一致性"


def test_restart_research_requires_explicit_confirmation() -> None:
    with pytest.raises(ValidationError):
        RestartResearchCommand(
            project_id="p1",
            command_id="c2",
            expected_version=2,
            confirm_restart=False,
            idea=INITIAL_INPUT,
        )


def test_decide_plan_can_continue_an_exhausted_candidate() -> None:
    parsed = TypeAdapter(Command).validate_python(
        {
            "type": "decide_plan",
            "project_id": "p1",
            "command_id": "continue-1",
            "expected_version": 1,
            "candidate_id": "candidate-2",
            "decision": {
                "decision": "continue_imperfect",
                "user_reason": "接受已记录的未解决风险",
            },
        }
    )

    assert parsed.decision.decision == "continue_imperfect"


@pytest.mark.asyncio
async def test_same_command_id_returns_original_receipt_without_reinvoking_handler(
    state,
) -> None:
    calls = 0

    async def handler(command, uow, project, session):
        nonlocal calls
        calls += 1
        run = AgentRun(
            run_id=f"run-{calls}",
            project_id=command.project_id,
            command_id=command.command_id,
            agent_name="idea_review",
            status="queued",
            attempt=0,
        )
        await uow.runs.add(run)
        from research_mentor.application.commands import AgentCommandReceipt

        return AgentCommandReceipt(
            project_id=command.project_id,
            command_id=command.command_id,
            run_id=run.run_id,
        )

    command_bus = CommandBus(
        lambda: FakeUow(state), handlers={"submit_idea": handler}, now=lambda: NOW
    )
    command = SubmitIdeaCommand(
        project_id="p1",
        command_id="c1",
        expected_version=1,
        idea=INITIAL_INPUT,
    )

    first = await command_bus.dispatch(command)
    state.projects["p1"] = state.projects["p1"].model_copy(update={"version": 2})
    second = await command_bus.dispatch(command)

    assert second == first
    assert second.command_id == "c1"
    assert second.run_id == first.run_id
    assert calls == 1
    assert len(state.runs) == 1


@pytest.mark.asyncio
async def test_sqlite_lock_on_recovery_lookup_is_retried(state, monkeypatch) -> None:
    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(
        "research_mentor.application.command_bus.asyncio.sleep", no_sleep
    )

    find_calls = {"n": 0}

    class LockingProcessed(ProcessedRepository):
        async def find(self, project_id, command_id):
            find_calls["n"] += 1
            if find_calls["n"] <= 2:
                raise OperationalError(
                    "SELECT", {}, Exception("database is locked")
                )
            return await super().find(project_id, command_id)

    class LockingUow(FakeUow):
        async def __aenter__(self):
            entered = await super().__aenter__()
            entered.processed_commands = LockingProcessed(self.state.processed)
            return entered

    async def handler(command, uow, project, session):
        return DeterministicCommandResult(
            project_id=project.project_id,
            command_id=command.command_id,
            session_id=session.session_id,
            version=project.version,
            phase=session.phase,
        )

    command_bus = CommandBus(
        lambda: LockingUow(state),
        handlers={"resume_working": handler},
        now=lambda: NOW,
    )
    command = TypeAdapter(Command).validate_python(
        {
            "type": "resume_working",
            "project_id": "p1",
            "command_id": "locked-1",
            "expected_version": 1,
        }
    )
    state.sessions["s1"] = ResearchSession(
        session_id="s1", phase=SessionPhase.AWAITING_RESULT_RECORD
    )

    result = await command_bus.dispatch(command)

    assert result.command_id == "locked-1"
    assert result.result_kind == "deterministic"


@pytest.mark.asyncio
async def test_agent_command_rejects_deterministic_handler_result(state) -> None:
    async def wrong_handler(command, uow, project, session):
        return DeterministicCommandResult(
            project_id=project.project_id,
            command_id=command.command_id,
            session_id=session.session_id,
            version=project.version,
            phase=session.phase,
        )

    command_bus = CommandBus(
        lambda: FakeUow(state),
        handlers={"submit_idea": wrong_handler},
        now=lambda: NOW,
    )

    with pytest.raises(InvariantViolationError, match="must return an agent receipt"):
        await command_bus.dispatch(
            SubmitIdeaCommand(
                project_id="p1",
                command_id="wrong-result",
                expected_version=1,
                idea=INITIAL_INPUT,
            )
        )


@pytest.mark.asyncio
async def test_version_and_phase_guards_run_before_handler(state) -> None:
    calls = 0

    async def handler(command, uow, project, session):
        nonlocal calls
        calls += 1
        return DeterministicCommandResult(
            project_id=project.project_id,
            command_id=command.command_id,
            session_id=session.session_id,
            version=project.version,
            phase=session.phase,
        )

    command_bus = CommandBus(
        lambda: FakeUow(state), handlers={"run_plan": handler}, now=lambda: NOW
    )

    with pytest.raises(ConcurrencyConflict):
        await command_bus.dispatch(
            RunPlanCommand(
                project_id="p1", command_id="stale", expected_version=2
            )
        )
    with pytest.raises(IllegalTransitionError):
        await command_bus.dispatch(
            RunPlanCommand(
                project_id="p1", command_id="wrong-phase", expected_version=1
            )
        )

    assert calls == 0
    assert state.processed == {}
    assert state.runs == {}


@pytest.mark.asyncio
async def test_active_run_blocks_new_idea_before_handler(state) -> None:
    state.runs["active"] = AgentRun(
        run_id="active",
        project_id="p1",
        command_id="old",
        agent_name="idea_review",
        status="running",
        attempt=1,
    )
    calls = 0

    async def handler(command, uow, project, session):
        nonlocal calls
        calls += 1
        raise AssertionError("handler must not run")

    command_bus = CommandBus(
        lambda: FakeUow(state), handlers={"submit_idea": handler}, now=lambda: NOW
    )

    with pytest.raises(IllegalTransitionError, match="run in progress"):
        await command_bus.dispatch(
            SubmitIdeaCommand(
                project_id="p1",
                command_id="new",
                expected_version=1,
                idea=INITIAL_INPUT,
            )
        )

    assert calls == 0
    assert len(state.runs) == 1


@pytest.mark.asyncio
async def test_restart_archives_cycle_by_switching_active_session_and_queues_review(
    state,
) -> None:
    state.sessions["s1"] = ResearchSession(
        session_id="s1", phase=SessionPhase.AWAITING_PLAN_DECISION
    )
    ids = iter(["s2", "run-restart", "event-restart", "outbox-restart"])
    restart_handler = RestartResearchHandler(
        new_id=lambda: next(ids), now=lambda: NOW
    )
    command_bus = CommandBus(
        lambda: FakeUow(state),
        handlers={"restart_research": restart_handler},
        now=lambda: NOW,
    )

    receipt = await command_bus.dispatch(
        RestartResearchCommand(
            project_id="p1",
            command_id="restart-1",
            expected_version=1,
            confirm_restart=True,
            idea=INITIAL_INPUT,
        )
    )

    assert receipt.run_id == "run-restart"
    assert state.projects["p1"].session_id == "s2"
    assert state.projects["p1"].version == 2
    assert state.sessions["s1"].phase is SessionPhase.AWAITING_PLAN_DECISION
    assert state.sessions["s2"].phase is SessionPhase.AWAITING_IDEA
    assert state.runs["run-restart"].agent_name == "idea_review"
    assert len(state.events) == 1
    assert len(state.outbox) == 1


@pytest.mark.asyncio
async def test_restart_is_atomic_with_existing_sql_uow(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'commands.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    old_session = ResearchSession(
        session_id="s1", phase=SessionPhase.AWAITING_PLAN_DECISION
    )
    async with factory.begin() as db:
        db.add(
            ProjectRow(
                project_id="p1",
                title="研究",
                domain="AI",
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
                phase=old_session.phase.value,
                updated_at=NOW,
                payload=old_session.model_dump(mode="json"),
            )
        )
    ids = iter(["s2", "run-restart", "event-restart", "outbox-restart"])
    bus = CommandBus(
        lambda: SqlUnitOfWork(factory),
        handlers={
            "restart_research": RestartResearchHandler(
                new_id=lambda: next(ids), now=lambda: NOW
            )
        },
        now=lambda: NOW,
    )

    await bus.dispatch(
        RestartResearchCommand(
            project_id="p1",
            command_id="restart-sql",
            expected_version=1,
            confirm_restart=True,
            idea=INITIAL_INPUT,
        )
    )

    async with factory() as db:
        project = await db.get(ProjectRow, "p1")
        assert project is not None
        assert project.session_id == "s2" and project.version == 2
        assert await db.scalar(select(func.count()).select_from(ResearchSessionRow)) == 2
        assert await db.scalar(select(func.count()).select_from(AgentRunRow)) == 1
        assert await db.scalar(select(func.count()).select_from(SessionEventRow)) == 1
        assert await db.scalar(select(func.count()).select_from(OutboxEventRow)) == 1
        assert await db.scalar(select(func.count()).select_from(ProcessedCommandRow)) == 1
    await engine.dispose()


async def create_sql_command_context(tmp_path, *, name: str):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / name}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session = ResearchSession(session_id="s1", phase=SessionPhase.AWAITING_IDEA)
    async with factory.begin() as db:
        db.add(
            ProjectRow(
                project_id="p1",
                title="研究",
                domain="AI",
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
    return engine, factory


def concurrent_agent_handler(calls: list[str]):
    async def handler(command, uow, project, session):
        calls.append(command.command_id)
        call_number = len(calls)
        await asyncio.sleep(0.05)
        run_id = f"run-{command.command_id}-{call_number}"
        event_id = f"event-{command.command_id}-{call_number}"
        await uow.runs.add(
            AgentRun(
                run_id=run_id,
                project_id=command.project_id,
                command_id=command.command_id,
                agent_name="idea_review",
                status="queued",
                attempt=0,
            )
        )
        await uow.events.append(
            SessionEvent(
                event_id=event_id,
                session_id=session.session_id,
                event_type=SessionEventType.IDEA_REVIEWED,
                phase_before=session.phase,
                phase_after=session.phase,
                payload={},
                occurred_at=NOW.isoformat(),
            )
        )
        await uow.outbox.append(
            OutboxEvent(
                outbox_id=f"outbox-{command.command_id}-{call_number}",
                session_event_id=event_id,
                project_id=command.project_id,
                topic="command.test",
                payload={},
                created_at=NOW,
            )
        )
        return AgentCommandReceipt(
            project_id=command.project_id,
            command_id=command.command_id,
            run_id=run_id,
        )

    return handler


@pytest.mark.asyncio
async def test_concurrent_same_command_returns_winner_receipt_and_runs_handler_once(
    tmp_path,
) -> None:
    engine, factory = await create_sql_command_context(
        tmp_path, name="same-command.db"
    )
    calls: list[str] = []
    bus = CommandBus(
        lambda: SqlUnitOfWork(factory),
        handlers={"submit_idea": concurrent_agent_handler(calls)},
        now=lambda: NOW,
    )
    command = SubmitIdeaCommand(
        project_id="p1",
        command_id="same",
        expected_version=1,
        idea=INITIAL_INPUT,
    )

    results = await asyncio.gather(
        bus.dispatch(command), bus.dispatch(command), return_exceptions=True
    )
    async with factory() as db:
        counts = tuple(
            [
                await db.scalar(select(func.count()).select_from(row_type))
                for row_type in (
                    AgentRunRow,
                    SessionEventRow,
                    OutboxEventRow,
                    ProcessedCommandRow,
                )
            ]
        )
    await engine.dispose()

    assert all(isinstance(item, AgentCommandReceipt) for item in results), results
    assert results[0] == results[1]
    assert calls == ["same"]
    assert counts == (1, 1, 1, 1)


@pytest.mark.asyncio
async def test_concurrent_agent_commands_with_same_version_reserve_only_one_run(
    tmp_path,
) -> None:
    engine, factory = await create_sql_command_context(
        tmp_path, name="different-commands.db"
    )
    calls: list[str] = []
    bus = CommandBus(
        lambda: SqlUnitOfWork(factory),
        handlers={"submit_idea": concurrent_agent_handler(calls)},
        now=lambda: NOW,
    )
    commands = [
        SubmitIdeaCommand(
            project_id="p1",
            command_id=command_id,
            expected_version=1,
            idea=INITIAL_INPUT,
        )
        for command_id in ("first", "second")
    ]

    results = await asyncio.gather(
        *(bus.dispatch(command) for command in commands), return_exceptions=True
    )
    async with factory() as db:
        run_count = await db.scalar(select(func.count()).select_from(AgentRunRow))
        processed_count = await db.scalar(
            select(func.count()).select_from(ProcessedCommandRow)
        )
    await engine.dispose()

    assert sum(isinstance(item, AgentCommandReceipt) for item in results) == 1, results
    assert sum(isinstance(item, ConcurrencyConflict) for item in results) == 1
    assert len(calls) == 1
    assert run_count == 1
    assert processed_count == 1
