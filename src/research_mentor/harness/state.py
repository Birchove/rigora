"""Harness-owned session state and event models."""

from enum import StrEnum

from pydantic import BaseModel, JsonValue

from research_mentor.harness.phase import SessionPhase
from research_mentor.harness.session_slices import (
    CompletionSlice,
    IdeaReviewSlice,
    PlanCheckSlice,
    PlanRevisionRecord,
    WorkingSlice,
)

__all__ = [
    "CompletionSlice",
    "IdeaReviewSlice",
    "PlanCheckSlice",
    "PlanRevisionRecord",
    "ResearchSession",
    "SessionEvent",
    "SessionEventType",
    "WorkingSlice",
]


class ResearchSession(IdeaReviewSlice, PlanCheckSlice, WorkingSlice, CompletionSlice):
    session_id: str
    phase: SessionPhase = SessionPhase.AWAITING_IDEA


class SessionEventType(StrEnum):
    SESSION_CREATED = "session_created"
    IDEA_REVIEWED = "idea_reviewed"
    PLAN_GENERATED = "plan_generated"
    KEY_INSIGHT_CHECKED = "key_insight_checked"
    PLAN_DECIDED = "plan_decided"
    WORKING_STARTED = "working_started"
    WORKING_TURN_COMPLETED = "working_turn_completed"
    WORKING_RESUMED = "working_resumed"
    WORKING_FINISHED = "working_finished"
    RESULT_RECORDED = "result_recorded"
    COMPLETE_GUIDANCE_GENERATED = "complete_guidance_generated"
    VALIDATIONS_SELECTED = "validations_selected"
    PLAN_REVISION_DECIDED = "plan_revision_decided"
    RUN_FAILED = "run_failed"
    DOCUMENT_PARSING_PROGRESS = "document_parsing_progress"


class SessionEvent(BaseModel):
    event_id: str
    session_id: str
    event_type: SessionEventType
    phase_before: SessionPhase | None
    phase_after: SessionPhase
    payload: dict[str, JsonValue]
    occurred_at: str
