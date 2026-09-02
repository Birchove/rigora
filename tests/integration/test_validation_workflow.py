"""Validation candidate queue, outcomes, and revision boundaries."""

import pytest

from research_mentor.domain.completion import ValidationCandidate, ValidationSelection
from research_mentor.domain.experiments import ValidationResult, ValidationTask
from research_mentor.errors import ValidationSelectionError
from research_mentor.harness.state import SessionPhase
from research_mentor.harness.validation import ValidationQueue


TASK = ValidationTask(
    paradigm="effectiveness",
    validation_type="ablation",
    name="消融",
    purpose="验证贡献",
    method="逐一移除模块",
)


def candidate(candidate_id: str, rank: int, priority: str = "high") -> ValidationCandidate:
    return ValidationCandidate(
        candidate_id=candidate_id,
        task=TASK,
        priority=priority,
        rank=rank,
        rationale=f"{candidate_id} 的导师理由",
        addresses_claims=["模块有效"],
    )


def test_candidates_are_offered_and_selected_by_rank() -> None:
    offered = ValidationQueue.from_candidates(
        [candidate("v2", 2), candidate("v1", 1), candidate("v3", 3)]
    )
    assert [item.candidate_id for item in offered.offered] == ["v1", "v2", "v3"]

    selected = offered.apply(
        ValidationSelection(selected_candidate_ids=["v3", "v1"], skipped_candidate_ids=["v2"])
    )
    assert [item.candidate.candidate_id for item in selected.selected] == ["v1", "v3"]
    assert selected.selected[0].status == "active"
    assert selected.selected[1].status == "pending"
    assert selected.next_phase is SessionPhase.WORKING


def test_duplicate_candidate_ids_are_rejected() -> None:
    with pytest.raises(ValidationSelectionError):
        ValidationQueue.from_candidates([candidate("dup", 1), candidate("dup", 2)])


@pytest.mark.parametrize(
    ("execution_status", "impact", "failure_reason"),
    [
        ("completed", "contradicts", None),
        ("failed", "neutral", "基准程序崩溃"),
        ("completed", "invalidates", None),
    ],
)
def test_validation_outcomes_are_recorded_without_collapsing_status(
    execution_status: str, impact: str, failure_reason: str | None
) -> None:
    result = ValidationResult(
        task=TASK,
        actual_result="如实记录",
        conclusion="按影响解释",
        is_success=False,
        execution_status=execution_status,
        impact=impact,
        failure_reason=failure_reason,
    )
    assert result.execution_status == execution_status
    assert result.impact == impact
    if execution_status == "invalidates" or impact == "invalidates":
        assert result.impact == "invalidates"


def test_critical_skip_keeps_mentor_and_user_reasons() -> None:
    result = ValidationQueue.from_candidates([candidate("critical-v1", 1, "critical")]).apply(
        ValidationSelection(
            skipped_candidate_ids=["critical-v1"],
            finish_without_more_validation=True,
            user_reason="没有额外 GPU",
        )
    )
    assert result.skipped[0].mentor_rationale == "critical-v1 的导师理由"
    assert result.skipped[0].user_reason == "没有额外 GPU"
    assert result.next_phase is SessionPhase.COMPLETING
