"""Research planning domain models."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from research_mentor.domain.evidence import EvidenceRef
from research_mentor.domain.checks import CheckRound
from research_mentor.domain.experiments import (
    ExperimentInfo,
    MainExperimentResult,
    ValidationResult,
)

NonBlankText = Annotated[str, StringConstraints(min_length=1)]
IdeaText = Annotated[str, StringConstraints(min_length=1, max_length=19999)]


def _reject_blank(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} 不能为空白字符串")


class InitialInput(BaseModel):
    original_idea: IdeaText
    domain: NonBlankText
    time_limit: str | None = None
    available_resources: list[str] = Field(default_factory=list)
    unavailable_resources: list[str] = Field(default_factory=list)
    other_constraints: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_required_text(self) -> Self:
        _reject_blank(self.original_idea, "original_idea")
        _reject_blank(self.domain, "domain")
        return self


class UserPlanFeedback(BaseModel):
    user_reason: str


class KnowledgeItem(BaseModel):
    topic: str
    reason: str
    references: list[EvidenceRef] = Field(default_factory=list)


class Milestone(BaseModel):
    name: str
    goal: str
    estimated_duration: str


class KeyInsight(BaseModel):
    title: str
    content: str
    rationale: str
    evidence: list[EvidenceRef] = Field(default_factory=list)


class ResearchPlan(BaseModel):
    research_question: str
    knowledge_requirements: list[KnowledgeItem]
    milestones: list[Milestone]
    key_insight: KeyInsight
    open_issues: list[str] = Field(default_factory=list)


PlanGenerationMode = Literal["low", "mid", "high"]
PlanCandidateDisposition = Literal[
    "active", "ready", "exhausted", "override", "selected", "archived"
]


class PlanCandidatePath(BaseModel):
    candidate_id: str
    candidate_index: int = Field(ge=1, le=3)
    model_profile: str
    focus_hint: str
    plan: ResearchPlan | None = None
    response_to_user: str | None = None
    change_summary: list[str] = Field(default_factory=list)
    check_history: list[CheckRound] = Field(default_factory=list)
    check_round: int = Field(default=0, ge=0)
    disposition: PlanCandidateDisposition = "active"


class PlanCandidateOverrideRecord(BaseModel):
    candidate_id: str
    final_score: float = Field(ge=0.0, le=10.0)
    unresolved_issues: list[str] = Field(default_factory=list)
    user_reason: NonBlankText
    timestamp: str


ForwardStage = Literal[
    "experiment_in_progress",
    "main_experiment_completed",
    "validation_in_progress",
    "research_completed",
]


class ForwardResearchContext(BaseModel):
    stage: ForwardStage
    research_question: str
    current_experiment: ExperimentInfo | None = None
    main_result: MainExperimentResult | None = None
    completed_validations: list[ValidationResult] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_stage_payload(self) -> Self:
        current_name = (
            self.current_experiment.current_experiment
            if self.current_experiment is not None
            else None
        )
        has_current = current_name is not None and bool(current_name.strip())
        if self.stage == "experiment_in_progress" and not has_current:
            raise ValueError("experiment_in_progress requires current_experiment")
        if self.stage in {"main_experiment_completed", "research_completed"}:
            if self.main_result is None:
                raise ValueError("completed stage requires main_result")
        if self.stage == "validation_in_progress":
            if self.main_result is None or not has_current:
                raise ValueError(
                    "validation_in_progress requires main_result and current_experiment"
                )
        return self


class ResearchContext(BaseModel):
    normalized_idea: str
    research_question: str
    plan: ResearchPlan | None = None
    forward_context: ForwardResearchContext | None = None

    @model_validator(mode="after")
    def validate_exactly_one_source(self) -> Self:
        if (self.plan is None) == (self.forward_context is None):
            raise ValueError("exactly one of plan or forward_context is required")
        return self


class UserPlanDecision(BaseModel):
    decision: Literal["accept", "override", "request_revision"]
    user_reason: str | None = None
    overridden_key_insight: KeyInsight | None = None

    @model_validator(mode="after")
    def validate_decision_shape(self) -> Self:
        if self.decision == "accept" and self.overridden_key_insight is not None:
            raise ValueError("accept 不得包含 overridden_key_insight")
        if self.decision == "request_revision":
            if self.user_reason is None or not self.user_reason.strip():
                raise ValueError("request_revision 必须包含非空 user_reason")
            if self.overridden_key_insight is not None:
                raise ValueError("request_revision 不得包含 overridden_key_insight")
        if self.decision == "override" and self.overridden_key_insight is None:
            raise ValueError("override 必须包含 overridden_key_insight")
        return self


class OverrideRecord(BaseModel):
    agent_recommendation: KeyInsight
    user_choice: KeyInsight
    agent_reason: str
    user_reason: str | None = None
    timestamp: str
