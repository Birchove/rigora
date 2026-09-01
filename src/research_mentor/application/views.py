"""Project creation and server-authoritative frontend views."""

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from research_mentor.application.allowed_commands import allowed_commands
from research_mentor.domain.projects import ResearchProject
from research_mentor.harness.phase import SessionPhase
from research_mentor.harness.state import (
    ResearchSession,
    SessionEvent,
    SessionEventType,
)
from research_mentor.ports.events import OutboxEvent


class ProjectView(BaseModel):
    project_id: str
    title: str
    domain: str
    version: int = Field(ge=1)
    phase: SessionPhase
    is_demo: bool = False
    allowed_commands: list[str]


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
        return self._to_view(project, session)

    async def get(self, project_id: str) -> ProjectView:
        async with self._uow_factory() as uow:
            project = await uow.projects.get(project_id)
            if project is None:
                raise ProjectNotFoundError(project_id)
            session = await uow.sessions.get(project.session_id)
            if session is None:
                raise ProjectNotFoundError(project_id)
        return self._to_view(project, session)

    async def list(self) -> list[ProjectView]:
        async with self._uow_factory() as uow:
            projects = await uow.projects.list()
            pairs = []
            for project in projects:
                session = await uow.sessions.get(project.session_id)
                if session is not None:
                    pairs.append((project, session))
        return [self._to_view(project, session) for project, session in pairs]

    @staticmethod
    def _to_view(project: ResearchProject, session: ResearchSession) -> ProjectView:
        return ProjectView(
            project_id=project.project_id,
            title=project.title,
            domain=project.domain,
            version=project.version,
            phase=session.phase,
            is_demo=project.is_demo,
            allowed_commands=list(allowed_commands(session)),
        )
