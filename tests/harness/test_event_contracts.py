"""Event payload and transition contracts using real orchestrator methods."""

from datetime import datetime, timezone
from uuid import UUID

from research_mentor.adapters.memory.clock import FixedClock
from research_mentor.adapters.memory.model import MemoryModelAdapter
from research_mentor.adapters.memory.repository import MemoryResearchSessionRepository
from research_mentor.agents.complete.contracts import CompleteAgentOutput
from research_mentor.agents.complete.runner import CompleteRunner
from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.agents.idea_review.runner import IdeaReviewRunner
from research_mentor.agents.key_insight_check.runner import KeyInsightCheckRunner
from research_mentor.agents.plan_loop.runner import PlanLoopRunner
from research_mentor.agents.working_qa.contracts import WorkingQAOutput
from research_mentor.agents.working_qa.runner import WorkingQARunner
from research_mentor.config import HarnessConfig
from research_mentor.domain.completion import WritingGuidance
from research_mentor.harness.scoring import finalize_key_insight_check
from research_mentor.domain.experiments import (
    ExperimentInfo,
    ExperimentTaskContext,
    MainExperimentResult,
    ValidationResult,
    ValidationTask,
)
from research_mentor.domain.research import (
    ForwardResearchContext,
    KeyInsight,
    OverrideRecord,
    UserPlanDecision,
)
from research_mentor.harness.orchestrator import ResearchMentorOrchestrator
from research_mentor.harness.state import ResearchSession, SessionEvent, SessionEventType, SessionPhase


FIXED_NOW = datetime(2026, 8, 30, 10, 0, tzinfo=timezone.utc)


def _bundle() -> tuple[ResearchMentorOrchestrator, MemoryModelAdapter, MemoryResearchSessionRepository]:
    model = MemoryModelAdapter()
    repository = MemoryResearchSessionRepository()
    return (
        ResearchMentorOrchestrator(
            repository=repository,
            clock=FixedClock(FIXED_NOW),
            idea_review_runner=IdeaReviewRunner(model),
            plan_loop_runner=PlanLoopRunner(model),
            key_insight_check_runner=KeyInsightCheckRunner(model),
            working_qa_runner=WorkingQARunner(model),
            complete_runner=CompleteRunner(model),
            config=HarnessConfig(),
        ),
        model,
        repository,
    )


def _opinion() -> IdeaReviewOutput:
    return IdeaReviewOutput(
        idea_type="opinion",
        action="proceed_to_plan",
        normalized_idea="比较状态压缩的恢复稳定性",
        reason="主张可以验证。",
        next_action="制定研究方案。",
    )


def _forward() -> IdeaReviewOutput:
    return IdeaReviewOutput(
        idea_type="forward",
        action="proceed_to_working",
        normalized_idea="已有状态压缩实验",
        reason="已有材料可开始工作。",
        next_action="进入实验问答。",
        forward_context=ForwardResearchContext(
            stage="experiment_in_progress",
            research_question="状态压缩能否提升恢复稳定性？",
            current_experiment=ExperimentInfo(current_experiment="比较状态压缩与基线"),
        ),
    )


def _main_task() -> ExperimentTaskContext:
    return ExperimentTaskContext(
        task_id="main-1",
        task_kind="main",
        origin="plan",
        status="in_progress",
        experiment_info=ExperimentInfo(
            current_experiment="比较状态压缩与基线",
            expected_result="压缩组更稳定",
        ),
    )


def _working_success() -> WorkingQAOutput:
    return WorkingQAOutput(
        action="success",
        reason="主实验已完成。",
        reply="",
        updated_experiment_info=ExperimentInfo(
            current_experiment="比较状态压缩与基线",
            expected_result="压缩组更稳定",
            actual_result="压缩组恢复正确率低于基线",
            observations=["固定切分下重复三次"],
        ),
    )


def _main_result() -> MainExperimentResult:
    return MainExperimentResult(
        objective="比较恢复正确率",
        method="固定数据切分与三次重复运行",
        expected_result="压缩组更稳定",
        actual_result="压缩组恢复正确率低于基线",
        conclusion="当前主实验不支持预期。",
        execution_status="completed",
        impact="contradicts",
    )


def _complete_output(plan: object) -> CompleteAgentOutput:
    return CompleteAgentOutput(
        mode="writing",
        plan=plan,
        final_hint="保留负面结果并说明局限。",
        writing_guidance=WritingGuidance(
            suggested_structure=["方法", "结果", "局限"],
            key_results_to_report=["恢复正确率低于基线"],
            key_discussion_points=["结果与预期相反"],
            limitations=["固定数据切分"],
        ),
    )


def _assert_event_metadata(events: list[SessionEvent]) -> None:
    assert len({event.event_id for event in events}) == len(events)
    for event in events:
        parsed_id = UUID(event.event_id)
        assert event.event_id
        assert parsed_id.version == 4
        assert str(parsed_id) == event.event_id
        occurred_at = datetime.fromisoformat(event.occurred_at)
        assert occurred_at.tzinfo is not None and occurred_at.utcoffset() is not None
        assert event.occurred_at == FIXED_NOW.isoformat()


def _reach_plan_decision(orchestrator, model, initial_input, plan_output, assessment):
    orchestrator.create_session("s1")
    review = _opinion()
    model.enqueue("idea_review", review)
    orchestrator.review_idea("s1", initial_input)
    model.enqueue("plan_loop", plan_output)
    orchestrator.run_plan_loop("s1")
    model.enqueue("key_insight_check", assessment)
    orchestrator.run_key_insight_check("s1")
    return review, plan_output, finalize_key_insight_check(assessment, HarnessConfig())


def _reach_completing(orchestrator, model, initial_input, plan_output, assessment):
    review, expected_plan, expected_check = _reach_plan_decision(
        orchestrator, model, initial_input, plan_output, assessment
    )
    decision = UserPlanDecision(decision="accept")
    orchestrator.decide_plan("s1", decision)
    task = _main_task()
    orchestrator.start_working("s1", task)
    working = _working_success()
    model.enqueue("working_qa", working)
    orchestrator.run_working_qa("s1", "请确认实验是否完成")
    result = _main_result()
    orchestrator.record_main_result("s1", result)
    return review, expected_plan, expected_check, decision, task, working, result


def test_main_accept_flow_emits_all_nine_exact_events(
    initial_input, plan_output, assessment
) -> None:
    orchestrator, model, repository = _bundle()
    review, expected_plan, expected_check, decision, task, working, result = _reach_completing(
        orchestrator, model, initial_input, plan_output, assessment
    )
    complete = _complete_output(plan_output.plan)
    model.enqueue("complete", complete)
    orchestrator.run_complete("s1", completion_status=True)

    events = repository.list_events("s1")
    assert [event.event_type for event in events] == [
        SessionEventType.SESSION_CREATED,
        SessionEventType.IDEA_REVIEWED,
        SessionEventType.PLAN_GENERATED,
        SessionEventType.KEY_INSIGHT_CHECKED,
        SessionEventType.PLAN_DECIDED,
        SessionEventType.WORKING_STARTED,
        SessionEventType.WORKING_TURN_COMPLETED,
        SessionEventType.RESULT_RECORDED,
        SessionEventType.COMPLETE_GUIDANCE_GENERATED,
    ]
    assert [(event.phase_before, event.phase_after) for event in events] == [
        (None, SessionPhase.AWAITING_IDEA),
        (SessionPhase.AWAITING_IDEA, SessionPhase.PLANNING),
        (SessionPhase.PLANNING, SessionPhase.CHECKING_KEY_INSIGHT),
        (SessionPhase.CHECKING_KEY_INSIGHT, SessionPhase.AWAITING_PLAN_DECISION),
        (SessionPhase.AWAITING_PLAN_DECISION, SessionPhase.AWAITING_WORKING_CONTEXT),
        (SessionPhase.AWAITING_WORKING_CONTEXT, SessionPhase.WORKING),
        (SessionPhase.WORKING, SessionPhase.AWAITING_RESULT_RECORD),
        (SessionPhase.AWAITING_RESULT_RECORD, SessionPhase.COMPLETING),
        (SessionPhase.COMPLETING, SessionPhase.COMPLETED),
    ]
    assert [event.payload for event in events] == [
        {},
        review.model_dump(mode="json"),
        expected_plan.model_dump(mode="json"),
        expected_check.model_dump(mode="json"),
        decision.model_dump(mode="json"),
        task.model_dump(mode="json"),
        working.model_dump(mode="json"),
        result.model_dump(mode="json"),
        {**complete.model_dump(mode="json"), "completion_status": True},
    ]
    _assert_event_metadata(events)


def test_override_and_forward_event_payload_extensions(
    initial_input, plan_output, assessment
) -> None:
    orchestrator, model, repository = _bundle()
    _reach_plan_decision(orchestrator, model, initial_input, plan_output, assessment)
    replacement = KeyInsight(
        title="用户指定路线", content="仅比较现有资源可运行的基线", rationale="资源限制"
    )
    decision = UserPlanDecision(
        decision="override",
        user_reason="实验资源有限",
        overridden_key_insight=replacement,
    )
    expected_check = finalize_key_insight_check(assessment, HarnessConfig())
    expected_record = OverrideRecord(
        agent_recommendation=plan_output.plan.key_insight,
        user_choice=replacement,
        agent_reason=expected_check.decision_reason,
        user_reason=decision.user_reason,
        timestamp=FIXED_NOW.isoformat(),
    )
    orchestrator.decide_plan("s1", decision)
    override_event = repository.list_events("s1")[-1]
    assert override_event.event_type is SessionEventType.PLAN_DECIDED
    assert override_event.phase_before is SessionPhase.AWAITING_PLAN_DECISION
    assert override_event.phase_after is SessionPhase.AWAITING_WORKING_CONTEXT
    assert override_event.payload == {
        **decision.model_dump(mode="json"),
        "override_record": expected_record.model_dump(mode="json"),
    }
    _assert_event_metadata(repository.list_events("s1"))

    forward_orchestrator, forward_model, forward_repository = _bundle()
    forward_orchestrator.create_session("forward")
    forward_output = _forward()
    forward_model.enqueue("idea_review", forward_output)
    forward_orchestrator.review_idea("forward", initial_input)
    start_event = forward_repository.list_events("forward")[-1]
    assert start_event.event_type is SessionEventType.IDEA_REVIEWED
    assert start_event.phase_before is SessionPhase.AWAITING_IDEA
    assert start_event.phase_after is SessionPhase.WORKING
    assert start_event.payload == forward_output.model_dump(mode="json")
    forward_session = forward_repository.get("forward")
    assert forward_session.current_task is not None
    assert forward_session.current_task.origin == "forward"
    assert forward_session.research_context is not None
    assert (
        forward_session.research_context.forward_context
        == forward_output.forward_context
    )
    _assert_event_metadata(forward_repository.list_events("forward"))


def test_validation_result_and_writing_completion_event_table_branches(
    initial_input, plan_output, assessment
) -> None:
    orchestrator, _, repository = _bundle()
    validation_task = ValidationTask(
        paradigm="effectiveness",
        validation_type="multiple_runs",
        name="重复运行",
        purpose="检查结果稳定性",
        method="固定切分重复五次",
    )
    validation_context = ExperimentTaskContext(
        task_id="validation-1",
        task_kind="validation",
        origin="validation_plan",
        status="completed",
        parent_task_id="main-1",
        validation_task=validation_task,
    )
    # AWAITING_VALIDATION_SELECTION has no specified continuation; seed only this
    # otherwise unreachable legal validation-result branch, then call the real method.
    seeded = ResearchSession(
        session_id="validation",
        phase=SessionPhase.AWAITING_RESULT_RECORD,
        current_task=validation_context,
        main_experiment=_main_result(),
    )
    repository.add(
        seeded,
        SessionEvent(
            event_id="seed-validation",
            session_id="validation",
            event_type=SessionEventType.SESSION_CREATED,
            phase_before=None,
            phase_after=SessionPhase.AWAITING_RESULT_RECORD,
            payload={},
            occurred_at=FIXED_NOW.isoformat(),
        ),
    )
    validation = ValidationResult(
        task=validation_task,
        actual_result="五次运行均复现负向结果",
        conclusion="负向结果稳定",
        is_success=True,
        execution_status="completed",
        impact="contradicts",
    )
    orchestrator.record_validation_result("validation", validation)
    validation_event = repository.list_events("validation")[-1]
    assert validation_event.event_type is SessionEventType.RESULT_RECORDED
    assert validation_event.phase_before is SessionPhase.AWAITING_RESULT_RECORD
    assert validation_event.phase_after is SessionPhase.COMPLETING
    assert validation_event.payload == validation.model_dump(mode="json")
    _assert_event_metadata([validation_event])

    complete_orchestrator, complete_model, complete_repository = _bundle()
    _reach_completing(
        complete_orchestrator, complete_model, initial_input, plan_output, assessment
    )
    complete = _complete_output(plan_output.plan)
    complete_model.enqueue("complete", complete)
    complete_orchestrator.run_complete("s1", completion_status=False)
    false_event = complete_repository.list_events("s1")[-1]
    assert false_event.event_type is SessionEventType.COMPLETE_GUIDANCE_GENERATED
    assert false_event.phase_before is SessionPhase.COMPLETING
    assert false_event.phase_after is SessionPhase.COMPLETED
    assert false_event.payload == {
        **complete.model_dump(mode="json"),
        "completion_status": False,
    }
    _assert_event_metadata(complete_repository.list_events("s1"))
