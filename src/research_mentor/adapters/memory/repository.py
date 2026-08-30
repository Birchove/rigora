"""In-memory research session repository."""

from research_mentor.errors import (
    DuplicateSessionError,
    InvariantViolationError,
    SessionNotFoundError,
)
from research_mentor.harness.state import ResearchSession, SessionEvent


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
