import pytest

from research_mentor.domain.completion import CompleteAgentOutput, WritingGuidance
from research_mentor.domain.research import KeyInsight, ResearchPlan
from research_mentor.harness.routing import route_complete
from research_mentor.harness.state import SessionPhase


PLAN = ResearchPlan(
    research_question="缓存是否降低尾延迟？",
    knowledge_requirements=[],
    milestones=[],
    key_insight=KeyInsight(title="分层缓存", content="比较尾延迟", rationale="可验证"),
)


@pytest.mark.parametrize(
    ("output", "phase"),
    [
        (
            CompleteAgentOutput(
                mode="validation",
                plan=PLAN,
                final_hint="选择验证",
                validation_candidates=[
                    {
                        "candidate_id": "v1",
                        "task": {
                            "paradigm": "effectiveness",
                            "validation_type": "ablation",
                            "name": "消融",
                            "purpose": "验证贡献",
                            "method": "移除模块",
                        },
                        "priority": "high",
                        "rank": 1,
                        "rationale": "需要隔离贡献",
                        "addresses_claims": ["模块有效"],
                    }
                ],
            ),
            SessionPhase.AWAITING_VALIDATION_SELECTION,
        ),
        (
            CompleteAgentOutput(
                mode="plan_revision",
                plan=PLAN,
                final_hint="需要修订",
                revision_reason="实验事实否定关键假设",
            ),
            SessionPhase.AWAITING_PLAN_REVISION_DECISION,
        ),
        (
            CompleteAgentOutput(
                mode="writing",
                plan=PLAN,
                final_hint="开始写作",
                writing_guidance=WritingGuidance(
                    suggested_structure=["方法", "结果"],
                    key_results_to_report=["尾延迟"],
                    key_discussion_points=["稳定性"],
                    limitations=["单一数据集"],
                ),
            ),
            SessionPhase.COMPLETED,
        ),
    ],
)
def test_complete_mode_routes_deterministically(output, phase: SessionPhase) -> None:
    decision = route_complete(output)

    assert decision.next_phase is phase
    assert decision.reason == output.final_hint
