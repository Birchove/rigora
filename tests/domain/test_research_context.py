import pytest
from pydantic import ValidationError

from research_mentor.domain.experiments import ExperimentInfo, MainExperimentResult
from research_mentor.domain.research import (
    ForwardResearchContext,
    KeyInsight,
    ResearchContext,
    ResearchPlan,
)


MAIN_RESULT = MainExperimentResult(
    objective="比较缓存策略",
    method="基准测试",
    actual_result="尾延迟下降 8%",
    conclusion="支持继续验证",
)
PLAN = ResearchPlan(
    research_question="缓存策略是否降低尾延迟？",
    knowledge_requirements=[],
    milestones=[],
    key_insight=KeyInsight(title="分层缓存", content="比较尾延迟", rationale="可验证"),
)


@pytest.mark.parametrize(
    ("stage", "current_experiment", "main_result"),
    [
        ("experiment_in_progress", ExperimentInfo(current_experiment="主实验"), None),
        ("main_experiment_completed", None, MAIN_RESULT),
        (
            "validation_in_progress",
            ExperimentInfo(current_experiment="鲁棒性验证"),
            MAIN_RESULT,
        ),
        ("research_completed", None, MAIN_RESULT),
    ],
)
def test_forward_research_context_accepts_each_complete_stage(
    stage: str,
    current_experiment: ExperimentInfo | None,
    main_result: MainExperimentResult | None,
) -> None:
    context = ForwardResearchContext(
        stage=stage,
        research_question="缓存策略是否降低尾延迟？",
        current_experiment=current_experiment,
        main_result=main_result,
    )

    assert context.stage == stage


@pytest.mark.parametrize(
    "payload",
    [
        {"stage": "experiment_in_progress"},
        {
            "stage": "experiment_in_progress",
            "current_experiment": ExperimentInfo(current_experiment="   "),
        },
        {"stage": "main_experiment_completed"},
        {"stage": "research_completed"},
        {"stage": "validation_in_progress", "main_result": MAIN_RESULT},
        {
            "stage": "validation_in_progress",
            "current_experiment": ExperimentInfo(current_experiment="验证"),
        },
    ],
)
def test_forward_research_context_rejects_incomplete_stage_payload(payload) -> None:
    with pytest.raises(ValidationError):
        ForwardResearchContext(
            research_question="缓存策略是否降低尾延迟？", **payload
        )


def test_research_context_requires_exactly_one_source() -> None:
    forward = ForwardResearchContext(
        stage="experiment_in_progress",
        research_question="缓存策略是否降低尾延迟？",
        current_experiment=ExperimentInfo(current_experiment="主实验"),
    )

    with pytest.raises(ValidationError):
        ResearchContext(
            normalized_idea="缓存研究",
            research_question="缓存策略是否降低尾延迟？",
        )
    with pytest.raises(ValidationError):
        ResearchContext(
            normalized_idea="缓存研究",
            research_question="缓存策略是否降低尾延迟？",
            plan=PLAN,
            forward_context=forward,
        )


def test_research_context_accepts_plan_or_forward_source() -> None:
    planned = ResearchContext(
        normalized_idea="缓存研究",
        research_question="缓存策略是否降低尾延迟？",
        plan=PLAN,
    )
    forwarded = ResearchContext(
        normalized_idea="缓存研究",
        research_question="缓存策略是否降低尾延迟？",
        forward_context=ForwardResearchContext(
            stage="experiment_in_progress",
            research_question="缓存策略是否降低尾延迟？",
            current_experiment=ExperimentInfo(current_experiment="主实验"),
        ),
    )

    assert planned.forward_context is None
    assert forwarded.plan is None
