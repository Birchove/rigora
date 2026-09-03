import pytest

from research_mentor.application.orchestration import SnapshotSessionRepository
from research_mentor.errors import SessionNotFoundError
from research_mentor.harness.phase import SessionPhase
from research_mentor.harness.state import ResearchSession, SessionEvent, SessionEventType


def _event(session_id: str, event_id: str = "event-1") -> SessionEvent:
    return SessionEvent(
        event_id=event_id,
        session_id=session_id,
        event_type=SessionEventType.SESSION_CREATED,
        phase_before=None,
        phase_after=SessionPhase.AWAITING_IDEA,
        payload={},
        occurred_at="2026-09-03T00:00:00+00:00",
    )


def test_snapshot_add_persists_session_and_event() -> None:
    seed = ResearchSession(session_id="s1")
    repository = SnapshotSessionRepository(seed)
    created = ResearchSession(session_id="s2")
    event = _event("s2")

    repository.add(created, event)

    assert repository.get("s2").session_id == "s2"
    assert [item.event_id for item in repository.list_events("s2")] == ["event-1"]
    assert repository.list_events("s2")[0].event_type is SessionEventType.SESSION_CREATED


def test_snapshot_add_rejects_mismatched_event_session() -> None:
    repository = SnapshotSessionRepository(ResearchSession(session_id="s1"))
    with pytest.raises(SessionNotFoundError):
        repository.add(ResearchSession(session_id="s1"), _event("other"))
