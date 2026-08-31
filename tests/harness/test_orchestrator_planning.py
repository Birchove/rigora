from datetime import datetime, timezone
import json

import pytest
from pydantic import ValidationError

from research_mentor.adapters.memory.clock import FixedClock
from research_mentor.adapters.memory.model import MemoryModelAdapter
from research_mentor.adapters.memory.repository import MemoryResearchSessionRepository
from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.agents.idea_review.runner import IdeaReviewRunner
from research_mentor.agents.key_insight_check.runner import KeyInsightCheckRunner
from research_mentor.agents.plan_loop.runner import PlanLoopRunner
from research_mentor.agents.complete.runner import CompleteRunner
from research_mentor.agents.working_qa.runner import WorkingQARunner
from research_mentor.config import HarnessConfig
from research_mentor.domain.checks import KeyInsightAssessment
from research_mentor.domain.experiments import (
    ExperimentInfo,
    ExperimentTaskContext,
    MainExperimentResult,
    ValidationResult,
    ValidationTask,
)
from research_mentor.domain.research import KeyInsight, UserPlanDecision
from research_mentor.errors import (
    IllegalTransitionError,
    InvariantViolationError,
    ModelOutputInvalid,
    PortExecutionError,
    SessionNotFoundError,
)
from research_mentor.harness.orchestrator import ResearchMentorOrchestrator
from research_mentor.harness.state import (
    ResearchSession,
    SessionEvent,
    SessionEventType,
    SessionPhase,
)


class RecordingMemoryModelAdapter(MemoryModelAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.calls = []

    async def generate(self, request):
        self.calls.append(request.model_copy(deep=True))
        return await super().generate(request)


def latest_payload(model: RecordingMemoryModelAdapter, agent_name: str, tag: str) -> dict:
    call = next(call for call in reversed(model.calls) if call.agent_name == agent_name)
    user_input = call.user_input
    assert isinstance(user_input, str)
    return json.loads(user_input.split(f"<{tag}>", 1)[1].rsplit(f"</{tag}>", 1)[0])


@pytest.fixture
def orchestration_bundle():
    model = RecordingMemoryModelAdapter()
    repository = MemoryResearchSessionRepository()
    orchestrator = ResearchMentorOrchestrator(
        repository=repository,
        clock=FixedClock(datetime(2026, 8, 29, 18, 0, tzinfo=timezone.utc)),
        idea_review_runner=IdeaReviewRunner(model),
        plan_loop_runner=PlanLoopRunner(model),
        key_insight_check_runner=KeyInsightCheckRunner(model),
        working_qa_runner=WorkingQARunner(model),
        complete_runner=CompleteRunner(model),
        config=HarnessConfig(),
    )
    return orchestrator, model, repository


def opinion_output() -> IdeaReviewOutput:
    return IdeaReviewOutput(
        idea_type="opinion",
        action="proceed_to_plan",
        normalized_idea="评估状态压缩对恢复稳定性的影响",
        reason="研究主张可验证。",
        next_action="制定研究方案。",
    )


def range_output() -> IdeaReviewOutput:
    return IdeaReviewOutput(
        idea_type="range",
        action="request_refinement",
        normalized_idea="Agent memory 的研究范围",
        reason="尚未形成可验证主张。",
        next_action="补充研究主张。",
    )


def failing_assessment(assessment: KeyInsightAssessment) -> KeyInsightAssessment:
    return assessment.model_copy(
        update={
            "scores": assessment.scores.model_copy(
                update={"novelty": assessment.scores.novelty.model_copy(update={"score": 1.0})}
            )
        },
        deep=True,
    )


def prepare_check(orchestration_bundle, initial_input, plan_output):
    orchestrator, model, repository = orchestration_bundle
    orchestrator.create_session("s1")
    model.enqueue("idea_review", opinion_output())
    orchestrator.review_idea("s1", initial_input)
    model.enqueue("plan_loop", plan_output)
    orchestrator.run_plan_loop("s1")
    return orchestrator, model, repository


def completed_phase_main_task() -> ExperimentTaskContext:
    return ExperimentTaskContext(
        task_id="main-1",
        task_kind="main",
        origin="forward",
        status="in_progress",
        experiment_info=ExperimentInfo(current_experiment="运行主实验"),
    )


def completed_phase_main_result() -> MainExperimentResult:
    return MainExperimentResult(
        objective="评估恢复稳定性",
        method="比较压缩与基线",
        actual_result="结果未支持假设",
        conclusion="当前设置下不成立",
        execution_status="completed",
        impact="contradicts",
    )


def completed_phase_validation_result() -> ValidationResult:
    return ValidationResult(
        task=ValidationTask(
            paradigm="robustness_reliability",
            validation_type="multiple_runs",
            name="重复运行验证",
            purpose="测量结果波动",
            method="运行十次并比较方差",
        ),
        actual_result="方差未降低",
        conclusion="未支持稳定性改善",
        is_success=False,
        execution_status="completed",
        impact="contradicts",
    )


def test_create_uses_exact_created_event_and_returns_defensive_copy(orchestration_bundle):
    orchestrator, _, repository = orchestration_bundle

    created = orchestrator.create_session("s1")
    created.phase = SessionPhase.REJECTED

    stored = repository.get("s1")
    event = repository.list_events("s1")[0]
    assert stored.phase is SessionPhase.AWAITING_IDEA
    assert event.event_type is SessionEventType.SESSION_CREATED
    assert event.phase_before is None
    assert event.phase_after is SessionPhase.AWAITING_IDEA
    assert event.payload == {}


def test_review_failure_keeps_session_and_event_history_unchanged(orchestration_bundle, initial_input):
    orchestrator, _, repository = orchestration_bundle
    orchestrator.create_session("s1")

    with pytest.raises(PortExecutionError):
        orchestrator.review_idea("s1", initial_input)

    assert repository.get("s1").phase is SessionPhase.AWAITING_IDEA
    assert [event.event_type for event in repository.list_events("s1")] == [SessionEventType.SESSION_CREATED]


@pytest.mark.parametrize(
    "command",
    [
        "review_idea",
        "run_plan_loop",
        "run_key_insight_check",
        "decide_plan",
        "start_working",
        "run_working_qa",
        "record_main_result",
        "record_validation_result",
        "run_complete",
    ],
)
def test_illegal_phase_rejects_every_public_command_without_runner_or_commit(
    orchestration_bundle, initial_input, command: str
):
    orchestrator, model, repository = orchestration_bundle
    repository.add(
        ResearchSession(session_id="s1", phase=SessionPhase.COMPLETED),
        SessionEvent(
            event_id="seed-completed",
            session_id="s1",
            event_type=SessionEventType.SESSION_CREATED,
            phase_before=None,
            phase_after=SessionPhase.COMPLETED,
            payload={},
            occurred_at="2026-08-29T18:00:00+00:00",
        ),
    )
    commands = {
        "review_idea": lambda: orchestrator.review_idea("s1", initial_input),
        "run_plan_loop": lambda: orchestrator.run_plan_loop("s1"),
        "run_key_insight_check": lambda: orchestrator.run_key_insight_check("s1"),
        "decide_plan": lambda: orchestrator.decide_plan(
            "s1", UserPlanDecision(decision="accept")
        ),
        "start_working": lambda: orchestrator.start_working(
            "s1", completed_phase_main_task()
        ),
        "run_working_qa": lambda: orchestrator.run_working_qa("s1", "当前状态如何？"),
        "record_main_result": lambda: orchestrator.record_main_result(
            "s1", completed_phase_main_result()
        ),
        "record_validation_result": lambda: orchestrator.record_validation_result(
            "s1", completed_phase_validation_result()
        ),
        "run_complete": lambda: orchestrator.run_complete("s1", completion_status=False),
    }
    before_session = repository.get("s1").model_dump(mode="json")
    before_events = [event.model_dump(mode="json") for event in repository.list_events("s1")]
    calls_before = len(model.calls)

    with pytest.raises(IllegalTransitionError):
        commands[command]()

    assert len(model.calls) == calls_before
    assert repository.get("s1").model_dump(mode="json") == before_session
    assert [event.model_dump(mode="json") for event in repository.list_events("s1")] == before_events


def test_idea_review_and_key_insight_check_use_fixed_shanghai_date(
    orchestration_bundle, initial_input, plan_output, assessment
):
    orchestrator, model, _ = orchestration_bundle
    orchestrator.create_session("s1")
    model.enqueue("idea_review", opinion_output())
    orchestrator.review_idea("s1", initial_input)
    review_call = next(call for call in reversed(model.calls) if call.agent_name == "idea_review")
    assert "## Current date\n2026-08-30" in review_call.instructions
    assert "sys_input" not in latest_payload(model, "idea_review", "idea_review_data")

    model.enqueue("plan_loop", plan_output)
    orchestrator.run_plan_loop("s1")
    model.enqueue("key_insight_check", assessment)
    orchestrator.run_key_insight_check("s1")
    check_call = next(
        call for call in reversed(model.calls) if call.agent_name == "key_insight_check"
    )
    assert "## Current date\n2026-08-30" in check_call.instructions
    assert "sys_input" not in latest_payload(
        model, "key_insight_check", "key_insight_check_data"
    )


def test_review_routes_range_and_records_exact_event(orchestration_bundle, initial_input):
    orchestrator, model, repository = orchestration_bundle
    orchestrator.create_session("s1")
    model.enqueue("idea_review", range_output())

    result = orchestrator.review_idea("s1", initial_input)

    event = repository.list_events("s1")[-1]
    assert result == range_output()
    assert repository.get("s1").phase is SessionPhase.AWAITING_IDEA_REFINEMENT
    assert event.event_type is SessionEventType.IDEA_REVIEWED
    assert event.phase_before is SessionPhase.AWAITING_IDEA
    assert event.phase_after is SessionPhase.AWAITING_IDEA_REFINEMENT
    assert event.payload == result.model_dump(mode="json")


def test_refinement_review_is_legal_and_emits_its_own_transition(
    orchestration_bundle, initial_input
):
    orchestrator, model, repository = orchestration_bundle
    orchestrator.create_session("s1")
    model.enqueue("idea_review", range_output())
    orchestrator.review_idea("s1", initial_input)
    model.enqueue("idea_review", opinion_output())

    orchestrator.review_idea("s1", initial_input)

    events = repository.list_events("s1")
    assert repository.get("s1").phase is SessionPhase.PLANNING
    assert [event.event_type for event in events] == [
        SessionEventType.SESSION_CREATED,
        SessionEventType.IDEA_REVIEWED,
        SessionEventType.IDEA_REVIEWED,
    ]
    assert [(event.phase_before, event.phase_after) for event in events[-2:]] == [
        (SessionPhase.AWAITING_IDEA, SessionPhase.AWAITING_IDEA_REFINEMENT),
        (SessionPhase.AWAITING_IDEA_REFINEMENT, SessionPhase.PLANNING),
    ]


def test_check_pass_waits_for_user_decision(orchestration_bundle, initial_input, plan_output, assessment):
    orchestrator, model, repository = prepare_check(orchestration_bundle, initial_input, plan_output)
    model.enqueue("key_insight_check", assessment)

    result = orchestrator.run_key_insight_check("s1")

    assert result.check_decision is True
    assert repository.get("s1").phase is SessionPhase.AWAITING_PLAN_DECISION


def test_initial_plan_rejects_change_summary_without_committing(
    orchestration_bundle, initial_input, plan_output
):
    orchestrator, model, repository = orchestration_bundle
    orchestrator.create_session("s1")
    model.enqueue("idea_review", opinion_output())
    orchestrator.review_idea("s1", initial_input)
    model.enqueue(
        "plan_loop",
        plan_output.model_copy(update={"change_summary": ["首次规划不应声称修订"]}, deep=True),
    )
    event_count = len(repository.list_events("s1"))

    with pytest.raises(InvariantViolationError):
        orchestrator.run_plan_loop("s1")

    stored = repository.get("s1")
    assert stored.phase is SessionPhase.PLANNING
    assert stored.latest_plan_output is None
    assert stored.active_plan is None
    assert len(repository.list_events("s1")) == event_count
    assert all(event.event_type is not SessionEventType.PLAN_GENERATED for event in repository.list_events("s1"))


def test_failed_checks_one_to_four_return_to_planning(orchestration_bundle, initial_input, plan_output, assessment):
    orchestrator, model, repository = prepare_check(orchestration_bundle, initial_input, plan_output)
    failed = failing_assessment(assessment)
    previous_output = None
    for round_number in range(1, 5):
        if round_number > 1:
            model.enqueue("plan_loop", plan_output)
            orchestrator.run_plan_loop("s1")
            payload = latest_payload(model, "plan_loop", "plan_loop_data")
            assert payload["previous_plan"] == plan_output.plan.model_dump(mode="json")
            assert payload["previous_insight_check"] == previous_output.model_dump(mode="json")
            assert payload["user_feedback"] is None
        model.enqueue("key_insight_check", failed)
        previous_output = orchestrator.run_key_insight_check("s1")
        stored = repository.get("s1")
        assert stored.phase is SessionPhase.PLANNING
        assert stored.check_round == round_number
        assert stored.latest_check == previous_output


def test_fifth_failed_check_is_persisted_and_exhausts_loop(orchestration_bundle, initial_input, plan_output, assessment):
    orchestrator, model, repository = prepare_check(orchestration_bundle, initial_input, plan_output)
    failed = failing_assessment(assessment)
    for round_number in range(1, 6):
        model.enqueue("key_insight_check", failed)
        orchestrator.run_key_insight_check("s1")
        if round_number < 5:
            model.enqueue("plan_loop", plan_output)
            orchestrator.run_plan_loop("s1")

    stored = repository.get("s1")
    assert stored.check_round == 5
    assert stored.latest_check is not None
    assert stored.phase is SessionPhase.CHECK_LOOP_EXHAUSTED


def test_sixth_check_is_rejected_without_model_call(orchestration_bundle, initial_input, plan_output, assessment):
    orchestrator, model, _ = prepare_check(orchestration_bundle, initial_input, plan_output)
    failed = failing_assessment(assessment)
    for round_number in range(1, 6):
        model.enqueue("key_insight_check", failed)
        orchestrator.run_key_insight_check("s1")
        if round_number < 5:
            model.enqueue("plan_loop", plan_output)
            orchestrator.run_plan_loop("s1")

    with pytest.raises(IllegalTransitionError):
        orchestrator.run_key_insight_check("s1")


def test_request_revision_stores_feedback_and_resets_cycle(orchestration_bundle, initial_input, plan_output, assessment):
    orchestrator, model, repository = prepare_check(orchestration_bundle, initial_input, plan_output)
    model.enqueue("key_insight_check", assessment)
    orchestrator.run_key_insight_check("s1")
    decision = UserPlanDecision(decision="request_revision", user_reason="缩小实验范围")

    result = orchestrator.decide_plan("s1", decision)

    assert result.phase is SessionPhase.PLANNING
    assert result.active_plan == plan_output.plan
    assert result.pending_plan_feedback is not None
    assert result.pending_plan_feedback.user_reason == "缩小实验范围"
    assert result.check_round == 0
    assert result.latest_check is None
    assert result.plan_decision is None
    assert repository.list_events("s1")[-1].payload == decision.model_dump(mode="json")


def test_accept_waits_for_working_context(orchestration_bundle, initial_input, plan_output, assessment):
    orchestrator, model, repository = prepare_check(orchestration_bundle, initial_input, plan_output)
    model.enqueue("key_insight_check", assessment)
    orchestrator.run_key_insight_check("s1")

    result = orchestrator.decide_plan("s1", UserPlanDecision(decision="accept"))

    assert result.phase is SessionPhase.AWAITING_WORKING_CONTEXT
    assert result.plan_decision is not None
    assert repository.get("s1") == result


def test_override_updates_both_plan_views_and_records_override(orchestration_bundle, initial_input, plan_output, assessment):
    orchestrator, model, repository = prepare_check(orchestration_bundle, initial_input, plan_output)
    model.enqueue("key_insight_check", assessment)
    check = orchestrator.run_key_insight_check("s1")
    replacement = KeyInsight(title="用户路线", content="用户指定的实验增量", rationale="现有资源可执行")
    decision = UserPlanDecision(
        decision="override", user_reason="现有资源仅支持该路线", overridden_key_insight=replacement
    )

    event_count = len(repository.list_events("s1"))
    result = orchestrator.decide_plan("s1", decision)
    stored = repository.get("s1")
    event = repository.list_events("s1")[-1]

    assert result.phase is SessionPhase.AWAITING_WORKING_CONTEXT
    assert stored.active_plan is not None and stored.active_plan.key_insight == replacement
    assert stored.latest_plan_output is not None and stored.latest_plan_output.plan.key_insight == replacement
    assert stored.override_record is not None
    assert stored.override_record.agent_recommendation == plan_output.plan.key_insight
    assert stored.override_record.agent_reason == check.decision_reason
    assert stored.override_record.user_choice == replacement
    assert stored.override_record.user_reason == decision.user_reason
    assert stored.override_record.timestamp == "2026-08-29T18:00:00+00:00"
    assert len(repository.list_events("s1")) == event_count + 1
    assert event.event_type is SessionEventType.PLAN_DECIDED
    assert event.payload == {
        **decision.model_dump(mode="json"),
        "override_record": stored.override_record.model_dump(mode="json"),
    }


class NaiveClock:
    def now(self):
        return datetime(2026, 8, 29, 18, 0)


def test_naive_clock_rejects_create_without_writing(orchestration_bundle):
    orchestrator, _, repository = orchestration_bundle
    orchestrator._clock = NaiveClock()

    with pytest.raises(InvariantViolationError):
        orchestrator.create_session("s1")

    with pytest.raises(SessionNotFoundError):
        repository.get("s1")


@pytest.mark.parametrize("mode", ["initial", "check_revision", "user_revision"])
def test_plan_derives_only_the_defined_input_mode(
    orchestration_bundle, initial_input, plan_output, assessment, mode: str
):
    _, model, repository = orchestration_bundle
    orchestrator = ResearchMentorOrchestrator(
        repository=repository,
        clock=FixedClock(datetime(2026, 8, 29, 18, 0, tzinfo=timezone.utc)),
        idea_review_runner=IdeaReviewRunner(model),
        plan_loop_runner=PlanLoopRunner(model),
        key_insight_check_runner=KeyInsightCheckRunner(model),
        working_qa_runner=WorkingQARunner(model),
        complete_runner=CompleteRunner(model),
        config=HarnessConfig(),
    )
    orchestrator.create_session("s1")
    model.enqueue("idea_review", opinion_output())
    orchestrator.review_idea("s1", initial_input)
    if mode == "check_revision":
        model.enqueue("plan_loop", plan_output)
        orchestrator.run_plan_loop("s1")
        model.enqueue("key_insight_check", failing_assessment(assessment))
        orchestrator.run_key_insight_check("s1")
    elif mode == "user_revision":
        model.enqueue("plan_loop", plan_output)
        orchestrator.run_plan_loop("s1")
        model.enqueue("key_insight_check", assessment)
        orchestrator.run_key_insight_check("s1")
        orchestrator.decide_plan(
            "s1", UserPlanDecision(decision="request_revision", user_reason="聚焦实验")
        )

    model.enqueue("plan_loop", plan_output)
    orchestrator.run_plan_loop("s1")

    request = latest_payload(model, "plan_loop", "plan_loop_data")
    assert request["check_round"] == (1 if mode == "check_revision" else 0)
    assert request["max_check_rounds"] == 5
    assert "loop_round" not in request
    assert "sys_input" not in request
    if mode == "initial":
        assert request["previous_plan"] is None
        assert request["previous_insight_check"] is None
        assert request["user_feedback"] is None
    elif mode == "check_revision":
        assert request["previous_plan"] == plan_output.plan.model_dump(mode="json")
        assert request["previous_insight_check"] is not None
        assert request["user_feedback"] is None
    else:
        assert request["previous_plan"] == plan_output.plan.model_dump(mode="json")
        assert request["previous_insight_check"] is None
        assert request["user_feedback"] == {"user_reason": "聚焦实验"}


def test_invalid_planning_combination_does_not_call_runner_or_commit(
    orchestration_bundle, initial_input, plan_output
):
    orchestrator, model, repository = orchestration_bundle
    session = ResearchSession(
        session_id="s1",
        phase=SessionPhase.PLANNING,
        initial_input=initial_input,
        idea_review=opinion_output(),
        active_plan=plan_output.plan,
    )
    repository.add(
        session,
        SessionEvent(
            event_id="seed",
            session_id="s1",
            event_type=SessionEventType.SESSION_CREATED,
            phase_before=None,
            phase_after=SessionPhase.PLANNING,
            payload={},
            occurred_at="2026-08-29T18:00:00+00:00",
        ),
    )
    count_before = len(repository.list_events("s1"))

    with pytest.raises(InvariantViolationError):
        orchestrator.run_plan_loop("s1")

    assert len(repository.list_events("s1")) == count_before
    assert repository.get("s1").phase is SessionPhase.PLANNING


@pytest.mark.parametrize("command", ["review", "plan", "check"])
def test_malformed_runner_outputs_leave_state_and_event_history_unchanged(
    orchestration_bundle, initial_input, plan_output, assessment, command: str
):
    orchestrator, model, repository = orchestration_bundle
    orchestrator.create_session("s1")
    if command == "review":
        model.enqueue(
            "idea_review",
            IdeaReviewOutput.model_construct(
                idea_type="bad", action="bad", normalized_idea="n", reason="r", next_action="n"
            ),
        )
        call = lambda: orchestrator.review_idea("s1", initial_input)
        expected_phase = SessionPhase.AWAITING_IDEA
    else:
        model.enqueue("idea_review", opinion_output())
        orchestrator.review_idea("s1", initial_input)
        if command == "plan":
            model.enqueue("plan_loop", plan_output.model_construct(plan="bad", response_to_user="r"))
            call = lambda: orchestrator.run_plan_loop("s1")
            expected_phase = SessionPhase.PLANNING
        else:
            model.enqueue("plan_loop", plan_output)
            orchestrator.run_plan_loop("s1")
            model.enqueue(
                "key_insight_check",
                assessment.model_construct(diagnostics="bad", scores="bad", reason="r", summary_advice="s"),
            )
            call = lambda: orchestrator.run_key_insight_check("s1")
            expected_phase = SessionPhase.CHECKING_KEY_INSIGHT
    count_before = len(repository.list_events("s1"))

    with pytest.raises(ModelOutputInvalid):
        call()

    assert repository.get("s1").phase is expected_phase
    assert len(repository.list_events("s1")) == count_before


def test_sixth_check_never_invokes_runner(
    initial_input, plan_output, assessment
):
    model = RecordingMemoryModelAdapter()
    repository = MemoryResearchSessionRepository()
    orchestrator = ResearchMentorOrchestrator(
        repository=repository,
        clock=FixedClock(datetime(2026, 8, 29, tzinfo=timezone.utc)),
        idea_review_runner=IdeaReviewRunner(model),
        plan_loop_runner=PlanLoopRunner(model),
        key_insight_check_runner=KeyInsightCheckRunner(model),
        working_qa_runner=WorkingQARunner(model),
        complete_runner=CompleteRunner(model),
        config=HarnessConfig(),
    )
    orchestrator.create_session("s1")
    model.enqueue("idea_review", opinion_output())
    orchestrator.review_idea("s1", initial_input)
    failed = failing_assessment(assessment)
    for round_number in range(1, 6):
        model.enqueue("plan_loop", plan_output)
        orchestrator.run_plan_loop("s1")
        model.enqueue("key_insight_check", failed)
        orchestrator.run_key_insight_check("s1")
        if round_number < 5:
            continue

    with pytest.raises(IllegalTransitionError):
        orchestrator.run_key_insight_check("s1")
    assert sum(call.agent_name == "key_insight_check" for call in model.calls) == 5


def test_public_results_cannot_mutate_persisted_plan_state(
    orchestration_bundle, initial_input, plan_output
):
    orchestrator, model, repository = orchestration_bundle
    orchestrator.create_session("s1")
    model.enqueue("idea_review", opinion_output())
    review = orchestrator.review_idea("s1", initial_input)
    review.reason = "mutated"
    model.enqueue("plan_loop", plan_output)
    output = orchestrator.run_plan_loop("s1")
    output.plan.key_insight.title = "mutated"

    stored = repository.get("s1")
    assert stored.idea_review is not None and stored.idea_review.reason == "研究主张可验证。"
    assert stored.active_plan is not None and stored.active_plan.key_insight.title == "分层状态压缩"


def test_successful_workflow_emits_one_exact_event_per_command(
    orchestration_bundle, initial_input, plan_output, assessment
):
    orchestrator, model, repository = orchestration_bundle
    orchestrator.create_session("s1")
    model.enqueue("idea_review", opinion_output())
    review = orchestrator.review_idea("s1", initial_input)
    model.enqueue("plan_loop", plan_output)
    plan = orchestrator.run_plan_loop("s1")
    model.enqueue("key_insight_check", assessment)
    check = orchestrator.run_key_insight_check("s1")
    decision = UserPlanDecision(decision="accept")
    returned_session = orchestrator.decide_plan("s1", decision)
    returned_session.active_plan.key_insight.title = "mutated"
    check.decision_reason = "mutated"

    events = repository.list_events("s1")
    assert [event.event_type for event in events] == [
        SessionEventType.SESSION_CREATED,
        SessionEventType.IDEA_REVIEWED,
        SessionEventType.PLAN_GENERATED,
        SessionEventType.KEY_INSIGHT_CHECKED,
        SessionEventType.PLAN_DECIDED,
    ]
    assert [(event.phase_before, event.phase_after) for event in events] == [
        (None, SessionPhase.AWAITING_IDEA),
        (SessionPhase.AWAITING_IDEA, SessionPhase.PLANNING),
        (SessionPhase.PLANNING, SessionPhase.CHECKING_KEY_INSIGHT),
        (SessionPhase.CHECKING_KEY_INSIGHT, SessionPhase.AWAITING_PLAN_DECISION),
        (SessionPhase.AWAITING_PLAN_DECISION, SessionPhase.AWAITING_WORKING_CONTEXT),
    ]
    assert [event.payload for event in events] == [
        {},
        review.model_dump(mode="json"),
        plan.model_dump(mode="json"),
        repository.get("s1").latest_check.model_dump(mode="json"),
        decision.model_dump(mode="json"),
    ]
    stored = repository.get("s1")
    assert stored.active_plan is not None and stored.active_plan.key_insight.title == "分层状态压缩"
    assert stored.latest_check is not None and stored.latest_check.decision_reason != "mutated"
