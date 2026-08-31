"""In-memory research session repository."""

from types import TracebackType
from typing import Self

from research_mentor.errors import (
    DuplicateSessionError,
    InvariantViolationError,
    SessionNotFoundError,
)
from research_mentor.harness.state import ResearchSession, SessionEvent
from research_mentor.ports.repository import ProcessedCommand


class MemoryProcessedCommandRepository:
    def __init__(
        self,
        commands: dict[tuple[str, str], ProcessedCommand] | None = None,
    ) -> None:
        self._commands = commands if commands is not None else {}

    async def find(
        self, project_id: str, command_id: str
    ) -> ProcessedCommand | None:
        command = self._commands.get((project_id, command_id))
        return command.model_copy(deep=True) if command is not None else None

    async def add(self, command: ProcessedCommand) -> None:
        key = (command.project_id, command.command_id)
        if key in self._commands:
            raise InvariantViolationError("Processed command already exists")
        self._commands[key] = command.model_copy(deep=True)


class MemoryRepositoryPort:
    """Small transactional UoW used by port contract tests."""

    def __init__(
        self,
        *,
        processed_commands: MemoryProcessedCommandRepository,
    ) -> None:
        self._stored_commands = processed_commands._commands
        self._working_commands: dict[tuple[str, str], ProcessedCommand] | None = None
        self.processed_commands = processed_commands

    async def __aenter__(self) -> Self:
        self._working_commands = {
            key: command.model_copy(deep=True)
            for key, command in self._stored_commands.items()
        }
        self.processed_commands = MemoryProcessedCommandRepository(
            self._working_commands
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is None and self._working_commands is not None:
            self._stored_commands.clear()
            self._stored_commands.update(self._working_commands)
        self._working_commands = None


class MemoryResearchSessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, ResearchSession] = {}
        self._events: dict[str, list[SessionEvent]] = {}

    def add(self, session: ResearchSession, event: SessionEvent) -> None:
        if session.session_id in self._sessions:
            raise DuplicateSessionError(f"Session already exists: {session.session_id}")
        self._validate_event_session_id(session, event)
        stored_session = session.model_copy(deep=True)
        stored_event = event.model_copy(deep=True)
        self._sessions[session.session_id] = stored_session
        self._events[session.session_id] = [stored_event]

    def get(self, session_id: str) -> ResearchSession:
        if session_id not in self._sessions:
            raise SessionNotFoundError(f"Session not found: {session_id}")
        return self._sessions[session_id].model_copy(deep=True)

    def commit(self, session: ResearchSession, event: SessionEvent) -> None:
        if session.session_id not in self._sessions:
            raise SessionNotFoundError(f"Session not found: {session.session_id}")
        self._validate_event_session_id(session, event)
        stored_session = session.model_copy(deep=True)
        stored_event = event.model_copy(deep=True)
        self._sessions[session.session_id] = stored_session
        self._events[session.session_id].append(stored_event)

    def list_events(self, session_id: str) -> list[SessionEvent]:
        if session_id not in self._sessions:
            raise SessionNotFoundError(f"Session not found: {session_id}")
        return [event.model_copy(deep=True) for event in self._events[session_id]]

    @staticmethod
    def _validate_event_session_id(session: ResearchSession, event: SessionEvent) -> None:
        if event.session_id != session.session_id:
            raise InvariantViolationError("Session event session_id must match session_id")
