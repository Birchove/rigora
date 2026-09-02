"""Harness-owned session state and event models."""

from enum import StrEnum

from pydantic import BaseModel, Field, JsonValue

from research_mentor.agents.complete.contracts import CompleteAgentOutput
from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.agents.plan_loop.contracts import PlanLoopOutput, PlanRevisionContext
from research_mentor.domain.checks import KeyInsightCheckOutput
from research_mentor.domain.experiments import (
    ExperimentTaskContext,
    MainExperimentResult,
    ValidationResult,
)
from research_mentor.domain.research import (
    InitialInput,
    OverrideRecord,
    PlanCandidatePath,
    PlanCandidateOverrideRecord,
    PlanGenerationMode,
    ResearchContext,
    ResearchPlan,
    UserPlanDecision,
    UserPlanFeedback,
)
from research_mentor.domain.completion import WritingGuidance
from research_mentor.harness.phase import SessionPhase
from research_mentor.harness.validation import ValidationQueue


class PlanRevisionRecord(BaseModel):
    decision: str
    mentor_reason: str
    user_reason: str | None = None


class ResearchSession(BaseModel):
    session_id: str
    phase: SessionPhase = SessionPhase.AWAITING_IDEA
    initial_input: InitialInput | None = None
    idea_review: IdeaReviewOutput | None = None
    research_context: ResearchContext | None = None
    refinement_code: str | None = None
    latest_plan_output: PlanLoopOutput | None = None
    active_plan: ResearchPlan | None = None
    latest_check: KeyInsightCheckOutput | None = None
    check_round: int = 0
    pending_plan_feedback: UserPlanFeedback | None = None
    pending_plan_revision_context: PlanRevisionContext | None = None
    plan_decision: UserPlanDecision | None = None
    override_record: OverrideRecord | None = None
    plan_generation_mode: PlanGenerationMode = "low"
    plan_candidates: list[PlanCandidatePath] = Field(default_factory=list)
    candidate_override_records: list[PlanCandidateOverrideRecord] = Field(
        default_factory=list
    )
    current_task: ExperimentTaskContext | None = None
    main_experiment: MainExperimentResult | None = None
    completed_validations: list[ValidationResult] = Field(default_factory=list)
    latest_complete_output: CompleteAgentOutput | None = None
    validation_queue: ValidationQueue | None = None
    writing_guidance: WritingGuidance | None = None
    plan_revision_records: list[PlanRevisionRecord] = Field(default_factory=list)
    pending_plan_issue_reason: str | None = None


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


class SessionEvent(BaseModel):
    event_id: str
    session_id: str
    event_type: SessionEventType
    phase_before: SessionPhase | None
    phase_after: SessionPhase
    payload: dict[str, JsonValue]
    occurred_at: str
