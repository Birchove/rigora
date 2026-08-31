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
from research_mentor.domain.research import KeyInsight, UserPlanDecision
from research_mentor.errors import InvariantViolationError
from research_mentor.harness.orchestrator import ResearchMentorOrchestrator
from research_mentor.harness.state import SessionPhase


@pytest.fixture
def bundle(initial_input):
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
