"""Research session persistence port."""

from typing import Protocol

from research_mentor.harness.state import ResearchSession, SessionEvent


class ResearchSessionRepository(Protocol):
    def add(self, session: ResearchSession, event: SessionEvent) -> None:
        raise NotImplementedError

    def get(self, session_id: str) -> ResearchSession:
        raise NotImplementedError

    def commit(self, session: ResearchSession, event: SessionEvent) -> None:
        raise NotImplementedError

    def list_events(self, session_id: str) -> list[SessionEvent]:
        raise NotImplementedError
