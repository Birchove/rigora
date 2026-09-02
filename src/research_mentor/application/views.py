"""Project creation and server-authoritative frontend views."""

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from research_mentor.application.allowed_commands import allowed_commands
from research_mentor.domain.completion import ValidationCandidate
from research_mentor.domain.jobs import AgentRun
from research_mentor.domain.projects import ResearchProject
from research_mentor.harness.phase import SessionPhase
from research_mentor.harness.state import (
    ResearchSession,
    SessionEvent,
    SessionEventType,
)
from research_mentor.ports.events import OutboxEvent


class ActiveRunView(BaseModel):
    run_id: str
    agent_name: str
    status: str
    public_message: str | None = None


class ProjectView(BaseModel):
    project_id: str
    title: str
    domain: str
    version: int = Field(ge=1)
    phase: SessionPhase
    is_demo: bool = False
    allowed_commands: list[str]
    last_event_sequence: int = 0
    active_run: ActiveRunView | None = None
    validation_candidates: list[ValidationCandidate] = Field(default_factory=list)


class ProjectNotFoundError(Exception):
    pass


class UnsupportedDomainError(Exception):
    pass


class ProjectViewService:
    def __init__(
        self,
        uow_factory,
        *,
        supported_domains: tuple[str, ...],
        supported_domain_aliases: tuple[str, ...],
        new_id: Callable[[], str] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._new_id = new_id or (lambda: str(uuid4()))
        self._now = now or (lambda: datetime.now(timezone.utc))
        canonical = supported_domains[0]
        self._domains = {
            value.strip().casefold(): canonical
            for value in (*supported_domains, *supported_domain_aliases)
        }

    async def create(self, *, title: str, domain: str) -> ProjectView:
        normalized_domain = self._domains.get(domain.strip().casefold())
        if normalized_domain is None:
            raise UnsupportedDomainError(domain)
        project_id = self._new_id()
        session_id = self._new_id()
        event_id = self._new_id()
        occurred_at = self._now()
        project = ResearchProject(
            project_id=project_id,
            title=title,
            domain=normalized_domain,
            session_id=session_id,
            version=1,
            created_at=occurred_at,
            updated_at=occurred_at,
        )
        session = ResearchSession(session_id=session_id)
        event = SessionEvent(
            event_id=event_id,
            session_id=session_id,
            event_type=SessionEventType.SESSION_CREATED,
            phase_before=None,
            phase_after=SessionPhase.AWAITING_IDEA,
            payload={},
            occurred_at=occurred_at.isoformat(),
        )
        async with self._uow_factory() as uow:
            await uow.projects.add(project)
            await uow.sessions.add(session, project_id=project_id)
            await uow.events.append(event)
            await uow.outbox.append(
                OutboxEvent(
                    outbox_id=self._new_id(),
                    session_event_id=event_id,
                    project_id=project_id,
                    topic="session.created",
                    payload={"session_id": session_id},
                    created_at=occurred_at,
                )
            )
        return self._to_view(project, session, active_run=None, last_event_sequence=1)

    async def get(self, project_id: str) -> ProjectView:
        async with self._uow_factory() as uow:
            project = await uow.projects.get(project_id)
            if project is None:
                raise ProjectNotFoundError(project_id)
            session = await uow.sessions.get(project.session_id)
            if session is None:
                raise ProjectNotFoundError(project_id)
            active_run = await uow.runs.find_active_for_project(project_id)
            last_event_sequence = await uow.events.latest_sequence(project_id)
        return self._to_view(
            project,
            session,
            active_run=active_run,
            last_event_sequence=last_event_sequence,
        )

    async def list(self) -> list[ProjectView]:
        async with self._uow_factory() as uow:
            projects = await uow.projects.list()
            views = []
            for project in projects:
                session = await uow.sessions.get(project.session_id)
                if session is None:
                    continue
                active_run = await uow.runs.find_active_for_project(project.project_id)
                last_event_sequence = await uow.events.latest_sequence(
                    project.project_id
                )
                views.append(
                    self._to_view(
                        project,
                        session,
                        active_run=active_run,
                        last_event_sequence=last_event_sequence,
                    )
                )
        return views

    @staticmethod
    def _to_view(
        project: ResearchProject,
        session: ResearchSession,
        *,
        active_run: AgentRun | None,
        last_event_sequence: int,
    ) -> ProjectView:
        offered = (
            session.validation_queue.offered if session.validation_queue is not None else []
        )
        return ProjectView(
            project_id=project.project_id,
            title=project.title,
            domain=project.domain,
            version=project.version,
            phase=session.phase,
            is_demo=project.is_demo,
            allowed_commands=list(allowed_commands(session)),
            last_event_sequence=last_event_sequence,
            active_run=(
                ActiveRunView(
                    run_id=active_run.run_id,
                    agent_name=active_run.agent_name,
                    status=active_run.status,
                    public_message=active_run.public_message,
                )
                if active_run is not None
                else None
            ),
            validation_candidates=[item.model_copy(deep=True) for item in offered],
        )
