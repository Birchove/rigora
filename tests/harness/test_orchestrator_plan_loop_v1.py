from datetime import datetime, timezone
import json

import pytest

from research_mentor.adapters.memory.clock import FixedClock
from research_mentor.adapters.memory.model import MemoryModelAdapter
from research_mentor.adapters.memory.repository import MemoryResearchSessionRepository
from research_mentor.agents.complete.contracts import CompleteAgentOutput
from research_mentor.agents.complete.runner import CompleteRunner
from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.agents.idea_review.runner import IdeaReviewRunner
from research_mentor.agents.key_insight_check.runner import KeyInsightCheckRunner
from research_mentor.agents.plan_loop.runner import PlanLoopRunner
from research_mentor.agents.working_qa.runner import WorkingQARunner
from research_mentor.agents.working_qa.contracts import WorkingQAOutput
from research_mentor.config import HarnessConfig
from research_mentor.domain.experiments import ExperimentInfo, MainExperimentResult
from research_mentor.domain.research import KeyInsight, UserPlanDecision
from research_mentor.errors import InvariantViolationError
from research_mentor.harness.orchestrator import ResearchMentorOrchestrator
from research_mentor.harness.state import SessionPhase


class RecordingModel(MemoryModelAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.calls = []

    async def generate(self, request):
        self.calls.append(request.model_copy(deep=True))
        return await super().generate(request)


@pytest.fixture
def bundle(initial_input):
    model = RecordingModel()
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
    model.enqueue(
        "idea_review",
        IdeaReviewOutput(
            idea_type="opinion",
            action="proceed_to_plan",
            normalized_idea="评估状态压缩",
            reason="可验证",
            next_action="制定方案",
        ),
    )
    orchestrator.review_idea("s1", initial_input)
    return orchestrator, model, repository


@pytest.mark.parametrize(("mode", "count"), [("low", 1), ("mid", 2), ("high", 3)])
def test_plan_mode_creates_isolated_candidate_paths(
    bundle, plan_output, mode: str, count: int
) -> None:
    orchestrator, model, _ = bundle
    for index in range(count):
        model.enqueue(
            "plan_loop",
            plan_output.model_copy(
                update={"response_to_user": f"candidate-{index + 1}"}, deep=True
            ),
        )

    session = orchestrator.run_plan("s1", mode=mode)

    assert len(session.plan_candidates) == count
    assert len({item.candidate_id for item in session.plan_candidates}) == count
    assert all(item.check_round == 0 for item in session.plan_candidates)
    assert len({item.focus_hint for item in session.plan_candidates}) == count
    assert session.plan_generation_mode == mode


def test_high_mode_rotates_plan_and_check_models(
    bundle, plan_output, assessment
) -> None:
    orchestrator, model, _ = bundle
    orchestrator._config = HarnessConfig(
        plan_check_pairs=(
            ("gpt-plan", "qwen-check"),
            ("qwen-plan", "glm-check"),
            ("glm-plan", "gpt-check"),
        )
    )
    for index in range(3):
        model.enqueue(
            "plan_loop",
            plan_output.model_copy(
                update={"response_to_user": f"candidate-{index + 1}"}, deep=True
            ),
        )

    session = orchestrator.run_plan("s1", mode="high")

    assert [item.plan_model_profile for item in session.plan_candidates] == [
        "gpt-plan",
        "qwen-plan",
        "glm-plan",
    ]
    assert [item.check_model_profile for item in session.plan_candidates] == [
        "qwen-check",
        "glm-check",
        "gpt-check",
    ]
    assert [
        call.model_profile for call in model.calls if call.agent_name == "plan_loop"
    ] == ["gpt-plan", "qwen-plan", "glm-plan"]

    for candidate in session.plan_candidates:
        model.enqueue("key_insight_check", assessment)
        session = orchestrator.run_check("s1", candidate_id=candidate.candidate_id)

    assert [
        call.model_profile
        for call in model.calls
        if call.agent_name == "key_insight_check"
    ] == ["qwen-check", "glm-check", "gpt-check"]


def test_high_mode_selects_exactly_one_candidate_and_preserves_others(
    bundle, plan_output, assessment
) -> None:
    orchestrator, model, _ = bundle
    for index in range(3):
        model.enqueue(
            "plan_loop",
            plan_output.model_copy(
                update={"response_to_user": f"candidate-{index + 1}"}, deep=True
            ),
        )
    session = orchestrator.run_plan("s1", mode="high")
    for candidate in session.plan_candidates:
        model.enqueue("key_insight_check", assessment)
        session = orchestrator.run_check("s1", candidate_id=candidate.candidate_id)

    selected_id = session.plan_candidates[1].candidate_id
    selected_plan = session.plan_candidates[1].plan
    decided = orchestrator.decide_plan(
        "s1", UserPlanDecision(decision="accept"), candidate_id=selected_id
    )

    assert decided.active_plan == selected_plan
    assert decided.phase is SessionPhase.WORKING
    assert decided.current_task is not None
    assert len(decided.plan_candidates) == 3
    assert [item.disposition for item in decided.plan_candidates].count("selected") == 1


def test_multi_candidate_decision_requires_candidate_id(
    bundle, plan_output, assessment
) -> None:
    orchestrator, model, _ = bundle
    for _ in range(2):
        model.enqueue("plan_loop", plan_output)
    session = orchestrator.run_plan("s1", mode="mid")
    for candidate in session.plan_candidates:
        model.enqueue("key_insight_check", assessment)
        session = orchestrator.run_check("s1", candidate_id=candidate.candidate_id)

    with pytest.raises(InvariantViolationError, match="candidate_id"):
        orchestrator.decide_plan("s1", UserPlanDecision(decision="accept"))


def test_exhausted_candidate_requires_explicit_override(
    bundle, plan_output, assessment
) -> None:
    orchestrator, model, _ = bundle
    orchestrator._config = HarnessConfig(max_check_rounds=1)
    model.enqueue("plan_loop", plan_output)
    session = orchestrator.run_plan("s1")
    failed = assessment.model_copy(
        update={
            "scores": assessment.scores.model_copy(
                update={
                    "novelty": assessment.scores.novelty.model_copy(
                        update={"score": 0.0}
                    )
                }
            )
        },
        deep=True,
    )
    model.enqueue("key_insight_check", failed)
    exhausted = orchestrator.run_check(
        "s1", candidate_id=session.plan_candidates[0].candidate_id
    )

    assert exhausted.phase is SessionPhase.CHECK_LOOP_EXHAUSTED
    overridden = orchestrator.continue_imperfect_plan(
        "s1", "candidate-1", user_reason="资源窗口有限"
    )

    assert overridden.plan_candidates[0].disposition == "override"
    assert overridden.candidate_override_records[-1].user_reason == "资源窗口有限"
    assert overridden.phase is SessionPhase.AWAITING_PLAN_DECISION


def test_candidate_key_insight_override_is_audited(
    bundle, plan_output, assessment
) -> None:
    orchestrator, model, _ = bundle
    model.enqueue("plan_loop", plan_output)
    session = orchestrator.run_plan("s1")
    model.enqueue("key_insight_check", assessment)
    orchestrator.run_check("s1", candidate_id=session.plan_candidates[0].candidate_id)
    replacement = KeyInsight(
        title="资源受限路线",
        content="只运行已有资源支持的对照",
        rationale="计算预算有限",
    )

    decided = orchestrator.decide_plan(
        "s1",
        UserPlanDecision(
            decision="override",
            user_reason="资源窗口即将关闭",
            overridden_key_insight=replacement,
        ),
    )

    assert decided.override_record is not None
    assert decided.override_record.user_reason == "资源窗口即将关闭"
    assert decided.active_plan is not None
    assert decided.active_plan.key_insight == replacement


def test_selected_candidate_result_revision_runs_without_user_reason(
    bundle, plan_output, assessment
) -> None:
    orchestrator, model, repository = bundle
    for index in range(2):
        model.enqueue(
            "plan_loop",
            plan_output.model_copy(
                update={"response_to_user": f"candidate-{index + 1}"}, deep=True
            ),
        )
    session = orchestrator.run_plan("s1", mode="mid")
    for candidate in session.plan_candidates:
        model.enqueue("key_insight_check", assessment)
        session = orchestrator.run_check("s1", candidate_id=candidate.candidate_id)
    selected_id = session.plan_candidates[1].candidate_id
    orchestrator.decide_plan(
        "s1", UserPlanDecision(decision="accept"), candidate_id=selected_id
    )
    model.enqueue(
        "working_qa",
        WorkingQAOutput(
            action="success", reason="主实验完成", reply="",
            updated_experiment_info=ExperimentInfo(
                current_experiment="主实验", actual_result="核心指标下降"
            ),
        ),
    )
    orchestrator.run_working_qa("s1", "主实验完成了吗？")
    result = MainExperimentResult(
        objective="检验恢复率",
        method="固定切分对照",
        actual_result="恢复率下降",
        conclusion="当前主张不成立",
        execution_status="completed",
        impact="invalidates",
    )
    orchestrator.record_main_result("s1", result)
    model.enqueue(
        "complete",
        CompleteAgentOutput(
            mode="plan_revision", plan=repository.get("s1").active_plan,
            final_hint="修订方案", revision_reason="主实验使核心主张失效",
        ),
    )
    orchestrator.run_complete("s1", completion_status=False)
    orchestrator.decide_plan_revision("s1", "revise")
    revised_output = plan_output.model_copy(
        update={"change_summary": ["依据负面主实验降低主张强度"]}, deep=True
    )
    model.enqueue("plan_loop", revised_output)

    revised = orchestrator.run_plan("s1")

    revised_candidate = next(
        item for item in revised.plan_candidates if item.candidate_id == selected_id
    )
    assert revised.phase is SessionPhase.CHECKING_KEY_INSIGHT
    assert revised_candidate.plan == revised_output.plan
    assert revised_candidate.disposition == "active"
    assert revised_candidate.check_round == 0
    assert revised_candidate.check_history == []
    assert revised.pending_plan_revision_context is None
    call = next(call for call in reversed(model.calls) if call.agent_name == "plan_loop")
    payload = json.loads(
        call.user_input.split("<plan_loop_data>", 1)[1].rsplit(
            "</plan_loop_data>", 1
        )[0]
    )
    assert payload["previous_plan"] == session.plan_candidates[1].plan.model_dump(
        mode="json"
    )
    assert payload["revision_context"]["mentor_issue_reason"] == (
        "主实验使核心主张失效"
    )
    assert payload["previous_insight_check"] is None
    assert payload["user_feedback"] is None

    model.enqueue("key_insight_check", assessment)
    checked = orchestrator.run_check("s1", candidate_id=selected_id)
    checked_candidate = next(
        item for item in checked.plan_candidates if item.candidate_id == selected_id
    )
    assert checked_candidate.disposition == "ready"
    assert checked.phase is SessionPhase.AWAITING_PLAN_DECISION
