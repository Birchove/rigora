"""Harness-owned validation candidate selection and queueing."""

from typing import Literal, Self

from pydantic import BaseModel, Field, ValidationError

from research_mentor.domain.completion import ValidationCandidate, ValidationSelection
from research_mentor.errors import ValidationSelectionError
from research_mentor.harness.state import SessionPhase


class QueuedValidation(BaseModel):
    candidate: ValidationCandidate
    status: Literal["active", "pending"] = "pending"


class SkippedValidation(BaseModel):
    candidate: ValidationCandidate
    mentor_rationale: str
    user_reason: str | None = None


class ValidationOverrideRecord(BaseModel):
    skipped_candidate_ids: list[str]
    user_reason: str


class ValidationQueue(BaseModel):
    offered: list[ValidationCandidate]
    selected: list[QueuedValidation] = Field(default_factory=list)
    skipped: list[SkippedValidation] = Field(default_factory=list)
    next_phase: SessionPhase | None = None
    override_record: ValidationOverrideRecord | None = None

    @classmethod
    def from_candidates(
        cls,
        candidates: list[ValidationCandidate],
        *,
        excluded_candidate_ids: set[str] | None = None,
    ) -> Self:
        excluded = excluded_candidate_ids or set()
        offered = [
            candidate.model_copy(deep=True)
            for candidate in candidates
            if candidate.candidate_id not in excluded
        ]
        candidate_ids = [candidate.candidate_id for candidate in offered]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValidationSelectionError("validation candidate IDs must be unique")
        return cls(offered=offered)

    def apply(self, selection: ValidationSelection) -> Self:
        try:
            selection = ValidationSelection.model_validate(
                selection.model_dump(mode="python")
            )
        except ValidationError as exc:
            raise ValidationSelectionError("invalid validation selection") from exc

        offered_by_id = {
            candidate.candidate_id: candidate for candidate in self.offered
        }
        selected_ids = selection.selected_candidate_ids.copy()
        skipped_ids = selection.skipped_candidate_ids.copy()
        previously_handled = {
            item.candidate.candidate_id for item in [*self.selected, *self.skipped]
        }
        if selection.finish_without_more_validation:
            explicitly_skipped = set(skipped_ids)
            skipped_ids.extend(
                candidate.candidate_id
                for candidate in self.offered
                if candidate.candidate_id not in previously_handled
                and candidate.candidate_id not in explicitly_skipped
            )
        requested_ids = set(selected_ids) | set(skipped_ids)
        unknown_ids = requested_ids - offered_by_id.keys()
        if unknown_ids:
            raise ValidationSelectionError(
                f"unknown validation candidate IDs: {sorted(unknown_ids)}"
            )

        if requested_ids & previously_handled:
            raise ValidationSelectionError("validation candidate was already handled")

        if not selection.finish_without_more_validation and not selected_ids:
            raise ValidationSelectionError("selection requires at least one candidate")

        selected_candidates = sorted(
            (offered_by_id[candidate_id] for candidate_id in selected_ids),
            key=lambda candidate: candidate.rank,
        )
        queued = [
            QueuedValidation(
                candidate=candidate.model_copy(deep=True),
                status="active" if index == 0 else "pending",
            )
            for index, candidate in enumerate(selected_candidates)
        ]
        skipped = [
            SkippedValidation(
                candidate=offered_by_id[candidate_id].model_copy(deep=True),
                mentor_rationale=offered_by_id[candidate_id].rationale,
                user_reason=selection.user_reason,
            )
            for candidate_id in skipped_ids
        ]

        if any(item.candidate.priority == "critical" for item in skipped):
            if selection.user_reason is None or not selection.user_reason.strip():
                raise ValidationSelectionError(
                    "skipping a critical candidate requires user_reason"
                )

        override_record = None
        next_phase = SessionPhase.WORKING
        if selection.finish_without_more_validation:
            next_phase = SessionPhase.COMPLETING
            override_record = ValidationOverrideRecord(
                skipped_candidate_ids=skipped_ids.copy(),
                user_reason=selection.user_reason or "",
            )

        return self.model_copy(
            update={
                "selected": [*self.selected, *queued],
                "skipped": [*self.skipped, *skipped],
                "next_phase": next_phase,
                "override_record": override_record,
            },
            deep=True,
        )
