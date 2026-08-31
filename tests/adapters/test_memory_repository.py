import inspect

import pytest
from pydantic import ValidationError

from research_mentor.adapters.memory.repository import MemoryResearchSessionRepository
from research_mentor.errors import (
    DuplicateSessionError,
    InvariantViolationError,
    SessionNotFoundError,
)
from research_mentor.harness.state import (
    ResearchSession,
    SessionEvent,
    SessionEventType,
    SessionPhase,
)
from research_mentor.ports.repository import ResearchSessionRepository


def event(session_id: str, event_id: str = "event-1") -> SessionEvent:
    return SessionEvent(
        event_id=event_id,
        session_id=session_id,
        event_type=SessionEventType.SESSION_CREATED,
        phase_before=None,
        phase_after=SessionPhase.AWAITING_IDEA,
        payload={},
        occurred_at="2026-08-29T10:00:00+08:00",
    )


def test_add_get_and_events_are_defensive_copies() -> None:
    repository = MemoryResearchSessionRepository()
    session = ResearchSession(session_id="session-1")
    repository.add(session, event("session-1"))

    loaded = repository.get("session-1")
    loaded.phase = SessionPhase.REJECTED
    loaded_events = repository.list_events("session-1")
    loaded_events[0].payload["changed"] = True

    assert repository.get("session-1").phase is SessionPhase.AWAITING_IDEA
    assert repository.list_events("session-1")[0].payload == {}


def test_commit_replaces_session_and_appends_one_event() -> None:
    repository = MemoryResearchSessionRepository()
    repository.add(ResearchSession(session_id="session-1"), event("session-1"))
    changed = repository.get("session-1")
    changed.phase = SessionPhase.REJECTED
    second = SessionEvent(
        event_id="event-2",
        session_id="session-1",
        event_type=SessionEventType.IDEA_REVIEWED,
        phase_before=SessionPhase.AWAITING_IDEA,
        phase_after=SessionPhase.REJECTED,
        payload={"action": "reject"},
        occurred_at="2026-08-29T10:01:00+08:00",
    )

    repository.commit(changed, second)

    assert repository.get("session-1").phase is SessionPhase.REJECTED
    assert [item.event_id for item in repository.list_events("session-1")] == [
        "event-1",
        "event-2",
    ]


def test_duplicate_add_and_missing_get_have_precise_errors() -> None:
    repository = MemoryResearchSessionRepository()
    repository.add(ResearchSession(session_id="session-1"), event("session-1"))

    with pytest.raises(DuplicateSessionError):
        repository.add(ResearchSession(session_id="session-1"), event("session-1", "e2"))
    with pytest.raises(SessionNotFoundError):
        repository.get("missing")


def test_session_phase_and_event_type_values_are_exact() -> None:
    assert {item.value for item in SessionPhase} == {
        "awaiting_idea",
        "awaiting_idea_refinement",
        "planning",
        "checking_key_insight",
        "awaiting_plan_decision",
        "awaiting_working_context",
        "working",
        "awaiting_result_record",
        "completing",
        "awaiting_validation_selection",
        "awaiting_plan_revision_decision",
        "completed",
        "rejected",
        "check_loop_exhausted",
    }
    assert {item.value for item in SessionEventType} == {
        "session_created",
        "idea_reviewed",
        "plan_generated",
        "key_insight_checked",
        "plan_decided",
        "working_started",
        "working_turn_completed",
        "result_recorded",
        "complete_guidance_generated",
    }


def test_research_session_defaults_are_complete_and_lists_are_isolated() -> None:
    first = ResearchSession(session_id="first")
    second = ResearchSession(session_id="second")

    assert first.phase is SessionPhase.AWAITING_IDEA
    assert first.initial_input is None
    assert first.idea_review is None
    assert first.latest_plan_output is None
    assert first.active_plan is None
    assert first.latest_check is None
    assert first.check_round == 0
    assert first.pending_plan_feedback is None
    assert first.plan_decision is None
    assert first.override_record is None
    assert first.current_task is None
    assert first.main_experiment is None
    assert first.completed_validations == []
    assert first.latest_complete_output is None

    first.completed_validations.append(object())  # type: ignore[arg-type]

    assert second.completed_validations == []


def test_session_event_payload_rejects_base_model_instances() -> None:
    with pytest.raises(ValidationError):
        SessionEvent(
            event_id="event-1",
            session_id="session-1",
            event_type=SessionEventType.SESSION_CREATED,
            phase_before=None,
            phase_after=SessionPhase.AWAITING_IDEA,
            payload={"session": ResearchSession(session_id="session-1")},
            occurred_at="2026-08-29T10:00:00+08:00",
        )


def test_add_defensively_copies_its_inputs() -> None:
    repository = MemoryResearchSessionRepository()
    session = ResearchSession(session_id="session-1")
    created = event("session-1")
    created.payload["details"] = {"status": "new"}

    repository.add(session, created)
    session.phase = SessionPhase.REJECTED
    created.payload["details"]["status"] = "changed"

    assert repository.get("session-1").phase is SessionPhase.AWAITING_IDEA
    assert repository.list_events("session-1")[0].payload == {
        "details": {"status": "new"}
    }


def test_commit_defensively_copies_its_inputs() -> None:
    repository = MemoryResearchSessionRepository()
    repository.add(ResearchSession(session_id="session-1"), event("session-1"))
    changed = repository.get("session-1")
    changed.phase = SessionPhase.REJECTED
    committed = event("session-1", "event-2")
    committed.payload["details"] = {"status": "committed"}

    repository.commit(changed, committed)
    changed.phase = SessionPhase.COMPLETED
    committed.payload["details"]["status"] = "changed"

    assert repository.get("session-1").phase is SessionPhase.REJECTED
    assert repository.list_events("session-1")[-1].payload == {
        "details": {"status": "committed"}
    }


def test_missing_commit_and_list_events_raise_session_not_found() -> None:
    repository = MemoryResearchSessionRepository()

    with pytest.raises(SessionNotFoundError):
        repository.commit(ResearchSession(session_id="missing"), event("missing"))
    with pytest.raises(SessionNotFoundError):
        repository.list_events("missing")


def test_mismatched_event_ids_leave_add_and_commit_state_unchanged() -> None:
    empty_repository = MemoryResearchSessionRepository()
    with pytest.raises(InvariantViolationError):
        empty_repository.add(ResearchSession(session_id="session-1"), event("other"))
    with pytest.raises(SessionNotFoundError):
        empty_repository.get("session-1")

    repository = MemoryResearchSessionRepository()
    repository.add(ResearchSession(session_id="session-1"), event("session-1"))
    changed = repository.get("session-1")
    changed.phase = SessionPhase.REJECTED

    with pytest.raises(InvariantViolationError):
        repository.commit(changed, event("other", "event-2"))

    assert repository.get("session-1").phase is SessionPhase.AWAITING_IDEA
    assert [item.event_id for item in repository.list_events("session-1")] == ["event-1"]


def test_repository_protocol_exposes_the_specified_methods() -> None:
    assert {
        name
        for name, value in ResearchSessionRepository.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"add", "get", "commit", "list_events"}

    add_signature = inspect.signature(ResearchSessionRepository.add)
    assert list(add_signature.parameters) == ["self", "session", "event"]
    assert add_signature.parameters["session"].annotation is ResearchSession
    assert add_signature.parameters["event"].annotation is SessionEvent
    assert add_signature.return_annotation is None

    get_signature = inspect.signature(ResearchSessionRepository.get)
    assert list(get_signature.parameters) == ["self", "session_id"]
    assert get_signature.parameters["session_id"].annotation is str
    assert get_signature.return_annotation is ResearchSession

    commit_signature = inspect.signature(ResearchSessionRepository.commit)
    assert list(commit_signature.parameters) == ["self", "session", "event"]
    assert commit_signature.parameters["session"].annotation is ResearchSession
    assert commit_signature.parameters["event"].annotation is SessionEvent
    assert commit_signature.return_annotation is None

    list_events_signature = inspect.signature(ResearchSessionRepository.list_events)
    assert list(list_events_signature.parameters) == ["self", "session_id"]
    assert list_events_signature.parameters["session_id"].annotation is str
    assert list_events_signature.return_annotation == list[SessionEvent]
