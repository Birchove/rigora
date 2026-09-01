"""Persistence boundaries for v1 application services."""

from datetime import datetime
from types import TracebackType
from typing import Protocol, Self

from pydantic import BaseModel, Field, JsonValue

from research_mentor.domain.documents import UploadedDocument
from research_mentor.domain.evidence import LiteratureRecord
from research_mentor.domain.jobs import AgentName, AgentRun
from research_mentor.domain.projects import ResearchProject
from research_mentor.harness.state import ResearchSession, SessionEvent
from research_mentor.ports.events import OutboxEvent


class ExpectedVersion(BaseModel):
    expected_version: int = Field(ge=1)


class ProcessedCommand(BaseModel):
    project_id: str
    command_id: str
    receipt: dict[str, JsonValue]
    run_id: str | None = None
    created_at: datetime


class AgentOutputRecord(BaseModel):
    output_id: str
    run_id: str
    project_id: str
    agent_name: AgentName
    prompt_version: str
    session_version: int = Field(ge=1)
    structured_payload: dict[str, JsonValue]
    created_at: datetime


class ProjectRepository(Protocol):
    async def add(self, project: ResearchProject) -> None: ...

    async def get(self, project_id: str) -> ResearchProject | None: ...

    async def list(self) -> list[ResearchProject]: ...

    async def save(self, project: ResearchProject, *, expected_version: int) -> None: ...


class SessionRepository(Protocol):
    async def add(self, session: ResearchSession, *, project_id: str) -> None: ...

    async def get(self, session_id: str) -> ResearchSession | None: ...

    async def save(self, session: ResearchSession, *, expected_version: int) -> None: ...


class ProcessedCommandRepository(Protocol):
    async def find(
        self, project_id: str, command_id: str
    ) -> ProcessedCommand | None: ...

    async def add(self, command: ProcessedCommand) -> None: ...


class AgentRunRepository(Protocol):
    async def get(self, run_id: str) -> AgentRun | None: ...

    async def add(self, run: AgentRun) -> None: ...

    async def save(self, run: AgentRun) -> None: ...

    async def find_active_for_project(self, project_id: str) -> AgentRun | None: ...

    async def claim_next(
        self, *, worker_id: str, now: datetime, lease_expires_at: datetime
    ) -> AgentRun | None: ...

    async def claim(
        self, run_id: str, *, worker_id: str, now: datetime, lease_expires_at: datetime
    ) -> AgentRun | None: ...

    async def renew_lease(
        self, run_id: str, *, worker_id: str, now: datetime, lease_expires_at: datetime
    ) -> AgentRun | None: ...

    async def request_cancel(self, run_id: str) -> bool: ...

    async def finish(
        self,
        run_id: str,
        *,
        worker_id: str,
        expected_version: int,
        status: str,
        now: datetime,
        public_message: str,
        error_code: str | None,
    ) -> bool: ...

    async def requeue_retry(
        self,
        run_id: str,
        *,
        worker_id: str,
        expected_version: int,
        available_at: datetime,
        public_message: str,
        error_code: str,
    ) -> bool: ...

    async def requeue_expired(self, *, now: datetime) -> tuple[str, ...]: ...


class DocumentRepository(Protocol):
    async def get(self, document_id: str) -> UploadedDocument | None: ...

    async def add(self, document: UploadedDocument) -> None: ...

    async def save(self, document: UploadedDocument) -> None: ...

    async def list_for_project(self, project_id: str) -> list[UploadedDocument]: ...


class LiteratureRepository(Protocol):
    async def add_many(
        self, project_id: str, records: list[LiteratureRecord]
    ) -> None: ...

    async def list_for_project(self, project_id: str) -> list[LiteratureRecord]: ...


class SessionEventRepository(Protocol):
    async def append(self, event: SessionEvent) -> None: ...

    async def list_for_session(self, session_id: str) -> list[SessionEvent]: ...


class OutboxRepository(Protocol):
    async def append(self, event: OutboxEvent) -> None: ...

    async def list_pending(self, *, limit: int) -> list[OutboxEvent]: ...

    async def mark_published(self, outbox_id: str, published_at: datetime) -> None: ...


class AgentOutputRepository(Protocol):
    async def add(self, output: AgentOutputRecord) -> None: ...

    async def list_for_run(self, run_id: str) -> list[AgentOutputRecord]: ...


class RepositoryPort(Protocol):
    projects: ProjectRepository
    sessions: SessionRepository
    processed_commands: ProcessedCommandRepository
    runs: AgentRunRepository
    documents: DocumentRepository
    literature: LiteratureRepository
    events: SessionEventRepository
    outbox: OutboxRepository
    agent_outputs: AgentOutputRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...


class ResearchSessionRepository(Protocol):
    """Compatibility port for the synchronous prototype orchestrator."""

    def add(self, session: ResearchSession, event: SessionEvent) -> None: ...

    def get(self, session_id: str) -> ResearchSession: ...

    def commit(self, session: ResearchSession, event: SessionEvent) -> None: ...

    def list_events(self, session_id: str) -> list[SessionEvent]: ...
