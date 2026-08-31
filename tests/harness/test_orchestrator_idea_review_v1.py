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


class RecordingMemoryModelAdapter(MemoryModelAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.calls = []

    async def generate(self, request):
        self.calls.append(request.model_copy(deep=True))
        return await super().generate(request)


@pytest.fixture
def bundle():
    model = RecordingMemoryModelAdapter()
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


def idea(domain: str = "computer science", text: str = "研究缓存一致性") -> InitialInput:
    return InitialInput(original_idea=text, domain=domain)


def main_result() -> MainExperimentResult:
    return MainExperimentResult(
        objective="比较缓存策略",
        method="运行基准测试",
        actual_result="尾延迟升高 8%",
        conclusion="当前策略未改善尾延迟",
        execution_status="completed",
        impact="contradicts",
    )


def validation_result() -> ValidationResult:
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


def forward_context(stage: str) -> ForwardResearchContext:
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
            main_result=main_result(),
        )
    return ForwardResearchContext(
        stage=stage,
        research_question="缓存策略是否降低尾延迟？",
        main_result=main_result(),
        completed_validations=[validation_result()] if stage == "research_completed" else [],
    )


def review_output(action: str, *, stage: str = "experiment_in_progress") -> IdeaReviewOutput:
    idea_type = {
        "proceed_to_plan": "opinion",
        "proceed_to_working": "forward",
        "request_refinement": "range",
        "reject": "opinion",
    }[action]
    return IdeaReviewOutput(
        idea_type=idea_type,
        action=action,
        normalized_idea="评估缓存策略",
        reason="路由理由",
        next_action="下一步",
        forward_context=forward_context(stage) if action == "proceed_to_working" else None,
    )


@pytest.mark.parametrize(
    ("action", "phase"),
    [
        ("proceed_to_plan", SessionPhase.PLANNING),
        ("proceed_to_working", SessionPhase.WORKING),
        ("request_refinement", SessionPhase.AWAITING_IDEA_REFINEMENT),
        ("reject", SessionPhase.REJECTED),
    ],
)
def test_review_action_has_single_route(bundle, action: str, phase: SessionPhase) -> None:
    orchestrator, model, repository = bundle
    model.enqueue("idea_review", review_output(action))

    orchestrator.review_idea("s1", idea())

    assert repository.get("s1").phase is phase


@pytest.mark.parametrize(
    "stage",
    [
        "experiment_in_progress",
        "main_experiment_completed",
        "validation_in_progress",
        "research_completed",
    ],
)
def test_forward_initializes_research_context_and_stage_task(bundle, stage: str) -> None:
    orchestrator, model, repository = bundle
    output = review_output("proceed_to_working", stage=stage)
    model.enqueue("idea_review", output)

    orchestrator.review_idea("s1", idea())

    session = repository.get("s1")
    assert session.phase is SessionPhase.WORKING
    assert session.research_context is not None
    assert session.research_context.forward_context == output.forward_context
    assert session.research_context.plan is None
    assert session.current_task is not None and session.current_task.origin == "forward"
    assert session.current_task.status == "in_progress"
    if stage == "experiment_in_progress":
        assert session.main_experiment is None
    else:
        assert session.main_experiment == main_result()
    if stage == "research_completed":
        assert session.completed_validations == [validation_result()]
    if stage in {"main_experiment_completed", "research_completed"}:
        assert (
            session.current_task.experiment_info.current_experiment
            == "核对已有结果与补充验证需求"
        )


def test_non_cs_domain_returns_refinement_without_model(bundle) -> None:
    orchestrator, model, repository = bundle

    output = orchestrator.review_idea("s1", idea(domain="biomedicine"))

    session = repository.get("s1")
    assert output.action == "request_refinement"
    assert session.phase is SessionPhase.AWAITING_IDEA_REFINEMENT
    assert session.refinement_code == "unsupported_domain"
    assert model.calls == []


def test_range_clarification_can_be_resubmitted(bundle) -> None:
    orchestrator, model, repository = bundle
    model.enqueue("idea_review", review_output("request_refinement"))
    orchestrator.review_idea("s1", idea(text="缓存研究"))
    model.enqueue("idea_review", review_output("proceed_to_plan"))

    orchestrator.review_idea("s1", idea(text="限定为数据库缓存一致性"))

    assert repository.get("s1").phase is SessionPhase.PLANNING
    assert repository.get("s1").initial_input == idea(text="限定为数据库缓存一致性")
