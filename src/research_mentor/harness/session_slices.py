"""Phase-scoped ResearchSession field groups.

These mixins flatten onto ResearchSession so persisted JSON keys stay unchanged.
"""

from pydantic import BaseModel, Field

from research_mentor.agents.complete.contracts import CompleteAgentOutput
from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.agents.plan_loop.contracts import PlanLoopOutput, PlanRevisionContext
from research_mentor.domain.checks import KeyInsightCheckOutput
from research_mentor.domain.completion import WritingGuidance
from research_mentor.domain.experiments import (
    ExperimentTaskContext,
    MainExperimentResult,
    ValidationResult,
)
from research_mentor.domain.research import (
    InitialInput,
    OverrideRecord,
    PlanCandidateOverrideRecord,
    PlanCandidatePath,
    PlanGenerationMode,
    ResearchContext,
    ResearchPlan,
    UserPlanDecision,
    UserPlanFeedback,
)
from research_mentor.harness.validation import ValidationQueue


class PlanRevisionRecord(BaseModel):
    decision: str
    mentor_reason: str
    user_reason: str | None = None


class IdeaReviewSlice(BaseModel):
    initial_input: InitialInput | None = None
    idea_review: IdeaReviewOutput | None = None
    research_context: ResearchContext | None = None
    refinement_code: str | None = None


class PlanCheckSlice(BaseModel):
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


class PendingWorkingClarification(BaseModel):
    original_question: str
    clarify_reply: str
    clarify_reason: str = ""


class WorkingSlice(BaseModel):
    current_task: ExperimentTaskContext | None = None
    pending_plan_issue_reason: str | None = None
    pending_working_clarification: PendingWorkingClarification | None = None


class CompletionSlice(BaseModel):
    main_experiment: MainExperimentResult | None = None
    completed_validations: list[ValidationResult] = Field(default_factory=list)
    latest_complete_output: CompleteAgentOutput | None = None
    validation_queue: ValidationQueue | None = None
    writing_guidance: WritingGuidance | None = None
    plan_revision_records: list[PlanRevisionRecord] = Field(default_factory=list)
