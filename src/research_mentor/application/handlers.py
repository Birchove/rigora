"""Handler contracts shared by the command bus and composition root."""

from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timezone
from typing import Any, TypeAlias
from uuid import uuid4

from research_mentor.application.commands import (
    AgentCommandReceipt,
    CancelRunCommand,
    CommandBase,
    CommandResult,
    DeterministicCommandResult,
    RestartResearchCommand,
)
from research_mentor.domain.jobs import AgentRun
from research_mentor.domain.projects import ResearchProject
from research_mentor.harness.phase import SessionPhase
from research_mentor.harness.state import (
    ResearchSession,
    SessionEvent,
    SessionEventType,
)
from research_mentor.ports.events import OutboxEvent
from research_mentor.errors import IllegalTransitionError
import logging


logger = logging.getLogger("research_mentor.runs")


CommandHandler: TypeAlias = Callable[
    [CommandBase, Any, ResearchProject, ResearchSession],
    Awaitable[CommandResult],
]
HandlerMap: TypeAlias = Mapping[str, CommandHandler]


AGENT_COMMAND_TYPES = frozenset(
    {
        "submit_idea",
        "submit_refinement",
        "run_plan",
        "run_check",
        "send_working_message",
        "submit_working_clarification",
        "run_complete",
        "restart_research",
    }
)


class RestartResearchHandler:
    """Atomically switch a project to a fresh cycle and queue Idea Review."""

    def __init__(
        self,
        *,
        new_id: Callable[[], str] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._new_id = new_id or (lambda: str(uuid4()))
        self._now = now or (lambda: datetime.now(timezone.utc))

    async def __call__(
        self,
        command: CommandBase,
        uow: Any,
        project: ResearchProject,
        session: ResearchSession,
    ) -> CommandResult:
        if not isinstance(command, RestartResearchCommand):
            raise TypeError("RestartResearchHandler requires restart_research")

        session_id = self._new_id()
        run_id = self._new_id()
        event_id = self._new_id()
        outbox_id = self._new_id()
        occurred_at = self._now()
        new_session = ResearchSession(
            session_id=session_id,
            phase=SessionPhase.AWAITING_IDEA,
            initial_input=command.idea.model_copy(deep=True),
        )
        await uow.sessions.add(new_session, project_id=project.project_id)

        updated_project = project.model_copy(
            update={
                "session_id": session_id,
                "updated_at": occurred_at,
            }
        )
        await uow.projects.save(updated_project, expected_version=project.version)

        await uow.runs.add(
            AgentRun(
                run_id=run_id,
                project_id=project.project_id,
                command_id=command.command_id,
                agent_name="idea_review",
                status="queued",
                attempt=0,
                input_snapshot=command.model_dump(mode="json"),
            )
        )
        event = SessionEvent(
            event_id=event_id,
            session_id=session_id,
            event_type=SessionEventType.SESSION_CREATED,
            phase_before=None,
            phase_after=SessionPhase.AWAITING_IDEA,
            payload={"previous_session_id": session.session_id},
            occurred_at=occurred_at.isoformat(),
        )
        await uow.events.append(event)
        await uow.outbox.append(
            OutboxEvent(
                outbox_id=outbox_id,
                session_event_id=event_id,
                project_id=project.project_id,
                topic="session.created",
                payload={
                    "session_id": session_id,
                    "previous_session_id": session.session_id,
                },
                created_at=occurred_at,
            )
        )
        return AgentCommandReceipt(
            project_id=project.project_id,
            command_id=command.command_id,
            run_id=run_id,
        )


class CancelRunHandler:
    """Record a cooperative cancellation request without unlocking the project."""

    async def __call__(
        self,
        command: CommandBase,
        uow: Any,
        project: ResearchProject,
        session: ResearchSession,
    ) -> CommandResult:
        if not isinstance(command, CancelRunCommand):
            raise TypeError("CancelRunHandler requires cancel_run")
        run = (
            await uow.runs.get(command.run_id)
            if command.run_id is not None
            else await uow.runs.find_active_for_project(project.project_id)
        )
        if (
            run is None
            or run.project_id != project.project_id
            or run.status not in {"queued", "running"}
            or not await uow.runs.request_cancel(run.run_id)
        ):
            raise IllegalTransitionError("no cancellable run")
        logger.info(
            "cancel requested project=%s run=%s status=%s",
            project.project_id,
            run.run_id,
            run.status,
        )
        return DeterministicCommandResult(
            project_id=project.project_id,
            command_id=command.command_id,
            session_id=session.session_id,
            version=project.version,
            phase=session.phase,
            payload={"run_id": run.run_id, "cancel_requested": True},
        )
