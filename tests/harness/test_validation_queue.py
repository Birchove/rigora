import pytest

from research_mentor.domain.completion import ValidationCandidate, ValidationSelection
from research_mentor.domain.experiments import ValidationTask
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


CANDIDATES = [candidate("v1", 1), candidate("v2", 2), candidate("v3", 3)]


def test_selected_candidates_are_queued_by_rank_not_request_order() -> None:
    selected = ValidationQueue.from_candidates(CANDIDATES).apply(
        ValidationSelection(
            selected_candidate_ids=["v3", "v1"],
            skipped_candidate_ids=["v2"],
        )
    )

    assert [item.candidate.candidate_id for item in selected.selected] == ["v1", "v3"]
    assert selected.next_phase is SessionPhase.WORKING


def test_finish_override_requires_user_reason() -> None:
    with pytest.raises(ValidationSelectionError):
        ValidationQueue.from_candidates(CANDIDATES).apply(
            ValidationSelection.model_construct(finish_without_more_validation=True)
        )


@pytest.mark.parametrize(
    "selection",
    [
        ValidationSelection(selected_candidate_ids=["unknown"]),
        ValidationSelection.model_construct(selected_candidate_ids=["v1", "v1"]),
        ValidationSelection.model_construct(
            selected_candidate_ids=["v1"], skipped_candidate_ids=["v1"]
        ),
    ],
)
def test_apply_rejects_unknown_duplicate_and_overlapping_ids(selection) -> None:
    with pytest.raises(ValidationSelectionError):
        ValidationQueue.from_candidates(CANDIDATES).apply(selection)


def test_skipping_critical_candidate_preserves_rationale_and_user_reason() -> None:
    queue = ValidationQueue.from_candidates([candidate("critical-v1", 1, "critical")])

    result = queue.apply(
        ValidationSelection(
            skipped_candidate_ids=["critical-v1"],
            finish_without_more_validation=True,
            user_reason="没有额外 GPU",
        )
    )

    assert result.next_phase is SessionPhase.COMPLETING
    assert result.skipped[0].candidate.priority == "critical"
    assert result.skipped[0].mentor_rationale == "critical-v1 的导师理由"
    assert result.skipped[0].user_reason == "没有额外 GPU"
    assert result.override_record is not None


def test_finish_implicitly_records_every_unhandled_candidate_as_skipped() -> None:
    result = ValidationQueue.from_candidates(CANDIDATES).apply(
        ValidationSelection(
            finish_without_more_validation=True,
            user_reason="项目时间已用完",
        )
    )

    assert [item.candidate.candidate_id for item in result.skipped] == [
        "v1",
        "v2",
        "v3",
    ]
    assert result.override_record is not None
    assert result.override_record.skipped_candidate_ids == ["v1", "v2", "v3"]
