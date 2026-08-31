"""Research completion and validation selection contracts."""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from research_mentor.domain.experiments import (
    ValidationParadigm,
    ValidationTask,
    ValidationType,
)
from research_mentor.domain.research import ResearchPlan


ValidationPriority = Literal["critical", "high", "medium", "low"]
CompletionMode = Literal["validation", "plan_revision", "writing"]


class ValidationCandidate(BaseModel):
    candidate_id: str
    task: ValidationTask
    priority: ValidationPriority
    rank: int = Field(ge=1)
    rationale: str
    addresses_claims: list[str]


class ExcludedValidation(BaseModel):
    paradigm: ValidationParadigm
    validation_type: ValidationType
    reason: str


class WritingGuidance(BaseModel):
    suggested_structure: list[str]
    key_results_to_report: list[str]
    key_discussion_points: list[str]
    limitations: list[str]


class CompleteAgentOutput(BaseModel):
    mode: CompletionMode
    plan: ResearchPlan | None
    final_hint: str
    validation_candidates: list[ValidationCandidate] = Field(default_factory=list)
    excluded_validations: list[ExcludedValidation] = Field(default_factory=list)
    writing_guidance: WritingGuidance | None = None
    revision_reason: str | None = None

    @model_validator(mode="after")
    def validate_mode_payload(self) -> Self:
        mode = getattr(self, "mode", None)
        if mode is None:
            raise ValueError("completion mode is required")
        candidate_ids = [item.candidate_id for item in self.validation_candidates]
        candidate_ranks = [item.rank for item in self.validation_candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("validation candidate IDs must be unique")
        if len(candidate_ranks) != len(set(candidate_ranks)):
            raise ValueError("validation candidate ranks must be unique")

        if mode == "validation":
            if not self.validation_candidates:
                raise ValueError("validation mode requires candidates")
            if self.writing_guidance is not None or self.revision_reason is not None:
                raise ValueError("validation mode rejects writing and revision payloads")
        elif mode == "plan_revision":
            if self.revision_reason is None or not self.revision_reason.strip():
                raise ValueError("plan_revision mode requires revision_reason")
            if (
                self.validation_candidates
                or self.excluded_validations
                or self.writing_guidance is not None
            ):
                raise ValueError("plan_revision mode only accepts revision_reason")
        else:
            if self.writing_guidance is None:
                raise ValueError("writing mode requires writing_guidance")
            if (
                self.validation_candidates
                or self.excluded_validations
                or self.revision_reason is not None
            ):
                raise ValueError("writing mode only accepts writing_guidance")
        return self


class ValidationSelection(BaseModel):
    selected_candidate_ids: list[str] = Field(default_factory=list)
    skipped_candidate_ids: list[str] = Field(default_factory=list)
    finish_without_more_validation: bool = False
    user_reason: str | None = None

    @model_validator(mode="after")
    def validate_selection(self) -> Self:
        selected = set(self.selected_candidate_ids)
        skipped = set(self.skipped_candidate_ids)
        if len(selected) != len(self.selected_candidate_ids):
            raise ValueError("selected candidate IDs must be unique")
        if len(skipped) != len(self.skipped_candidate_ids):
            raise ValueError("skipped candidate IDs must be unique")
        if selected & skipped:
            raise ValueError("selected and skipped candidates must not overlap")
        if self.finish_without_more_validation:
            if self.selected_candidate_ids:
                raise ValueError("finish selection cannot select candidates")
            if self.user_reason is None or not self.user_reason.strip():
                raise ValueError("finish selection requires user_reason")
        return self
