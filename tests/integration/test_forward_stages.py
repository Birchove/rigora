"""Four ForwardStage entries skip Plan Loop and initialize Working from existing facts."""

from datetime import datetime, timezone

import pytest

from research_mentor.adapters.memory.clock import FixedClock
from research_mentor.adapters.memory.model import MemoryModelAdapter
from research_mentor.adapters.memory.repository import MemoryResearchSessionRepository
from research_mentor.agents.complete.runner import CompleteRunner
from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.agents.idea_review.runner import IdeaReviewRunner
from research_mentor.agents.key_insight_check.runner import KeyInsightCheckRunner
from research_mentor.agents.plan_loop.runner import PlanLoopRunner
from research_mentor.agents.working_qa.runner import WorkingQARunner
from research_mentor.config import HarnessConfig
from research_mentor.domain.experiments import (
    ExperimentInfo,
    MainExperimentResult,
    ValidationResult,
    ValidationTask,
)
from research_mentor.domain.research import ForwardResearchContext, InitialInput
from research_mentor.harness.orchestrator import ResearchMentorOrchestrator
from research_mentor.harness.state import SessionPhase


def _idea() -> InitialInput:
    return InitialInput(original_idea="缓存策略是否降低尾延迟？", domain="computer science")


def _main_result() -> MainExperimentResult:
    return MainExperimentResult(
        objective="比较缓存策略",
        method="运行基准测试",
        actual_result="尾延迟升高 8%",
        conclusion="当前策略未改善尾延迟",
        execution_status="completed",
        impact="contradicts",
    )


def _validation_result() -> ValidationResult:
    return ValidationResult(
        task=ValidationTask(
            paradigm="robustness_reliability",
            validation_type="multiple_runs",
            name="重复运行",
            purpose="检查波动",
            method="重复十次",
        ),
        actual_result="波动仍然存在",
        conclusion="结果稳定",
        is_success=True,
        execution_status="completed",
        impact="supports",
    )


def _forward_context(stage: str) -> ForwardResearchContext:
    if stage == "experiment_in_progress":
        return ForwardResearchContext(
            stage=stage,
            research_question="缓存策略是否降低尾延迟？",
            current_experiment=ExperimentInfo(current_experiment="运行缓存基准"),
        )
    if stage == "validation_in_progress":
        return ForwardResearchContext(
            stage=stage,
            research_question="缓存策略是否降低尾延迟？",
            current_experiment=ExperimentInfo(current_experiment="重复运行验证"),
            main_result=_main_result(),
        )
    return ForwardResearchContext(
        stage=stage,
        research_question="缓存策略是否降低尾延迟？",
        main_result=_main_result(),
        completed_validations=[_validation_result()] if stage == "research_completed" else [],
    )


@pytest.fixture
def bundle():
    model = MemoryModelAdapter()
    repository = MemoryResearchSessionRepository()
    orchestrator = ResearchMentorOrchestrator(
        repository=repository,
        clock=FixedClock(datetime(2026, 8, 31, tzinfo=timezone.utc)),
        idea_review_runner=IdeaReviewRunner(model),
        plan_loop_runner=PlanLoopRunner(model),
        key_insight_check_runner=KeyInsightCheckRunner(model),
        working_qa_runner=WorkingQARunner(model),
        complete_runner=CompleteRunner(model),
        config=HarnessConfig(),
    )
    orchestrator.create_session("s1")
    return orchestrator, model, repository


@pytest.mark.parametrize(
    "stage",
    [
        "experiment_in_progress",
        "main_experiment_completed",
        "validation_in_progress",
        "research_completed",
    ],
)
def test_each_forward_stage_skips_plan_loop_and_enters_working(bundle, stage: str) -> None:
    orchestrator, model, repository = bundle
    output = IdeaReviewOutput(
        idea_type="forward",
        action="proceed_to_working",
        normalized_idea="评估缓存策略",
        reason="前向研究信息完整。",
        next_action="进入 Working。",
        forward_context=_forward_context(stage),
    )
    model.enqueue("idea_review", output)

    orchestrator.review_idea("s1", _idea())

    session = repository.get("s1")
    assert session.phase is SessionPhase.WORKING
    assert session.research_context is not None
    assert session.research_context.plan is None
    assert session.research_context.forward_context is not None
    assert session.research_context.forward_context.stage == stage
    assert session.current_task is not None
    assert session.current_task.origin == "forward"
    assert session.current_task.status == "in_progress"
    assert all(request.agent_name != "plan_loop" for request in model.requests)
    if stage == "experiment_in_progress":
        assert session.main_experiment is None
        assert session.current_task.experiment_info.current_experiment == "运行缓存基准"
    else:
        assert session.main_experiment == _main_result()
    if stage == "validation_in_progress":
        assert session.current_task.experiment_info.current_experiment == "重复运行验证"
    if stage in {"main_experiment_completed", "research_completed"}:
        assert (
            session.current_task.experiment_info.current_experiment
            == "核对已有结果与补充验证需求"
        )
