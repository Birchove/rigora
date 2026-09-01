"""Harness session phases shared by state and transition helpers."""

from enum import StrEnum


class SessionPhase(StrEnum):
    AWAITING_IDEA = "awaiting_idea"
    AWAITING_IDEA_REFINEMENT = "awaiting_idea_refinement"
    PLANNING = "planning"
    CHECKING_KEY_INSIGHT = "checking_key_insight"
    AWAITING_PLAN_DECISION = "awaiting_plan_decision"
    AWAITING_WORKING_CONTEXT = "awaiting_working_context"
    WORKING = "working"
    AWAITING_RESULT_RECORD = "awaiting_result_record"
    COMPLETING = "completing"
    AWAITING_VALIDATION_SELECTION = "awaiting_validation_selection"
    AWAITING_PLAN_REVISION_DECISION = "awaiting_plan_revision_decision"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CHECK_LOOP_EXHAUSTED = "check_loop_exhausted"
