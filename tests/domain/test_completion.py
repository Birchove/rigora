import pytest
from pydantic import ValidationError

from research_mentor.domain.completion import (
    CompleteAgentOutput,
    ValidationCandidate,
    ValidationSelection,
    WritingGuidance,
)
from research_mentor.domain.experiments import ValidationTask
from research_mentor.domain.research import KeyInsight, ResearchPlan


PLAN = ResearchPlan(
    research_question="缓存策略是否降低尾延迟？",
    knowledge_requirements=[],
    milestones=[],
    key_insight=KeyInsight(title="分层缓存", content="比较尾延迟", rationale="可验证"),
)
TASK = ValidationTask(
    paradigm="robustness_reliability",
    validation_type="multiple_runs",
    name="重复运行",
    purpose="验证方差",
    method="固定种子重复十次",
)


def candidate(candidate_id: str = "v1", rank: int = 1) -> ValidationCandidate:
    return ValidationCandidate(
        candidate_id=candidate_id,
        task=TASK,
        priority="critical",
        rank=rank,
        rationale="核心结论依赖稳定性",
        addresses_claims=["尾延迟稳定下降"],
    )


def test_validation_mode_requires_ranked_unique_candidates() -> None:
    with pytest.raises(ValidationError):
        CompleteAgentOutput(mode="validation", plan=PLAN, final_hint="选择验证")
    with pytest.raises(ValidationError):
        CompleteAgentOutput(
            mode="validation",
            plan=PLAN,
            final_hint="选择验证",
            validation_candidates=[candidate("v1", 1), candidate("v2", 1)],
        )
    with pytest.raises(ValidationError):
        CompleteAgentOutput(
            mode="validation",
            plan=PLAN,
            final_hint="选择验证",
            validation_candidates=[candidate("v1", 1), candidate("v1", 2)],
        )


def test_plan_revision_and_writing_modes_require_exclusive_payloads() -> None:
    with pytest.raises(ValidationError):
        CompleteAgentOutput(mode="plan_revision", plan=PLAN, final_hint="修订")
    with pytest.raises(ValidationError):
        CompleteAgentOutput(mode="writing", plan=PLAN, final_hint="写作")

    writing = CompleteAgentOutput(
        mode="writing",
        plan=PLAN,
        final_hint="开始整理结果",
        writing_guidance=WritingGuidance(
            suggested_structure=["方法", "结果"],
            key_results_to_report=["尾延迟下降 8%"],
            key_discussion_points=["稳定性"],
            limitations=["仅一个数据集"],
        ),
    )
    assert writing.validation_candidates == []


def test_finish_without_validation_requires_reason_and_no_selection() -> None:
    with pytest.raises(ValidationError):
        ValidationSelection(
            selected_candidate_ids=["v1"],
            finish_without_more_validation=True,
            user_reason="资源不足",
        )
    with pytest.raises(ValidationError):
        ValidationSelection(finish_without_more_validation=True)


def test_validation_selection_rejects_selected_skipped_overlap() -> None:
    with pytest.raises(ValidationError):
        ValidationSelection(
            selected_candidate_ids=["v1"], skipped_candidate_ids=["v1"]
        )
