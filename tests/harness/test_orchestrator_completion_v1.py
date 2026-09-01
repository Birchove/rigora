from datetime import datetime, timezone

import pytest

from research_mentor.adapters.memory.clock import FixedClock
from research_mentor.adapters.memory.model import MemoryModelAdapter
from research_mentor.adapters.memory.repository import MemoryResearchSessionRepository
from research_mentor.agents.complete.contracts import CompleteAgentOutput
from research_mentor.agents.complete.runner import CompleteRunner
from research_mentor.agents.idea_review.runner import IdeaReviewRunner
from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.agents.key_insight_check.runner import KeyInsightCheckRunner
from research_mentor.agents.plan_loop.runner import PlanLoopRunner
from research_mentor.agents.working_qa.contracts import WorkingQAOutput
from research_mentor.agents.working_qa.runner import WorkingQARunner
from research_mentor.config import HarnessConfig
from research_mentor.domain.completion import ValidationCandidate, ValidationSelection, WritingGuidance
from research_mentor.domain.experiments import (
    ExperimentInfo,
    ExperimentTaskContext,
    MainExperimentResult,
    ValidationResult,
    ValidationTask,
)
from research_mentor.domain.research import ForwardResearchContext, ResearchContext
from research_mentor.errors import InvariantViolationError
from research_mentor.harness.orchestrator import ResearchMentorOrchestrator
from research_mentor.harness.state import SessionEventType, SessionPhase


class RecordingModel(MemoryModelAdapter):
    def __init__(self):
        super().__init__()
        self.calls = []

    async def generate(self, request):
        self.calls.append(request.model_copy(deep=True))
        return await super().generate(request)


@pytest.fixture
def completion_bundle(initial_input):
    model = RecordingModel()
    repository = MemoryResearchSessionRepository()
    orchestrator = ResearchMentorOrchestrator(
        repository=repository,
        clock=FixedClock(datetime(2026, 9, 1, tzinfo=timezone.utc)),
        idea_review_runner=IdeaReviewRunner(model),
        plan_loop_runner=PlanLoopRunner(model),
        key_insight_check_runner=KeyInsightCheckRunner(model),
        working_qa_runner=WorkingQARunner(model),
        complete_runner=CompleteRunner(model),
        config=HarnessConfig(),
    )
    orchestrator.create_session("s1")
    forward = ForwardResearchContext(
        stage="experiment_in_progress",
        research_question="压缩是否改善恢复稳定性？",
        current_experiment=ExperimentInfo(current_experiment="主实验"),
    )
    session = repository.get("s1")
    session.initial_input = initial_input
    session.idea_review = IdeaReviewOutput(
        idea_type="forward", action="proceed_to_working",
        normalized_idea="评估压缩恢复稳定性", reason="已有实验", next_action="继续实验",
        forward_context=forward,
    )
    session.research_context = ResearchContext(
        normalized_idea="评估压缩恢复稳定性",
        research_question=forward.research_question,
        forward_context=forward,
    )
    session.current_task = ExperimentTaskContext(
        task_id="main-1",
        task_kind="main",
        origin="forward",
        status="in_progress",
        experiment_info=forward.current_experiment,
    )
    session.phase = SessionPhase.WORKING
    repository.commit(
        session,
        repository.list_events("s1")[-1].model_copy(
            update={"event_id": "seed-forward", "phase_after": SessionPhase.WORKING}
        ),
    )
    return orchestrator, model, repository


def main_result() -> MainExperimentResult:
    return MainExperimentResult(
        objective="比较恢复率",
        method="固定切分重复运行",
        actual_result="恢复率下降",
        conclusion="不支持预期",
        execution_status="completed",
        impact="contradicts",
    )


def candidate(candidate_id: str, rank: int) -> ValidationCandidate:
    return ValidationCandidate(
        candidate_id=candidate_id,
        task=ValidationTask(
            paradigm="robustness_reliability",
            validation_type="multiple_runs",
            name=f"重复运行 {candidate_id}",
            purpose="检查稳定性",
            method="重复十次",
        ),
        priority="critical" if rank == 1 else "high",
        rank=rank,
        rationale=f"导师理由 {candidate_id}",
        addresses_claims=["恢复稳定性"],
    )


def propose_success(orchestrator, model):
    model.enqueue(
        "working_qa",
        WorkingQAOutput(
            action="success",
            reason="任务可能完成",
            reply="",
            updated_experiment_info=ExperimentInfo(
                current_experiment="主实验", actual_result="恢复率下降"
            ),
        ),
    )
    orchestrator.run_working_qa("s1", "完成了吗？")


def test_success_is_proposal_and_resume_is_deterministic(completion_bundle):
    orchestrator, model, repository = completion_bundle
    propose_success(orchestrator, model)

    proposed = repository.get("s1")
    assert proposed.phase is SessionPhase.AWAITING_RESULT_RECORD
    assert proposed.current_task.status == "in_progress"
    call_count = len(model.calls)

    resumed = orchestrator.resume_working("s1")

    assert resumed.phase is SessionPhase.WORKING
    assert resumed.current_task.status == "in_progress"
    assert len(model.calls) == call_count
    assert repository.list_events("s1")[-1].event_type is SessionEventType.WORKING_RESUMED


def test_record_main_result_confirms_task_and_forward_runs_complete(completion_bundle):
    orchestrator, model, repository = completion_bundle
    propose_success(orchestrator, model)

    recorded = orchestrator.record_main_result("s1", main_result())

    assert recorded.phase is SessionPhase.COMPLETING
    assert recorded.current_task.status == "completed"
    assert recorded.active_plan is None
    output = CompleteAgentOutput(
        mode="writing",
        plan=None,
        final_hint="进入写作",
        writing_guidance=WritingGuidance(
            suggested_structure=["结果"],
            key_results_to_report=["恢复率下降"],
            key_discussion_points=["负面结果"],
            limitations=["单数据集"],
        ),
    )
    model.enqueue("complete", output)
    orchestrator.run_complete("s1", completion_status=True)
    stored = repository.get("s1")
    assert stored.phase is SessionPhase.COMPLETED
    assert stored.writing_guidance == output.writing_guidance
    complete_call = [call for call in model.calls if call.agent_name == "complete"][-1]
    assert '"research_context"' in complete_call.user_input
    assert '"plan": null' in complete_call.user_input


def test_report_plan_issue_is_main_only(completion_bundle):
    orchestrator, model, repository = completion_bundle
    model.enqueue(
        "working_qa",
        WorkingQAOutput(action="report_plan_issue", reason="核心假设已被推翻", reply="需要修订方案"),
    )
    orchestrator.run_working_qa("s1", "结果推翻了假设")
    assert repository.get("s1").phase is SessionPhase.AWAITING_PLAN_REVISION_DECISION

    stored = repository.get("s1")
    stored.phase = SessionPhase.WORKING
    stored.current_task = ExperimentTaskContext(
        task_id="v-task", task_kind="validation", origin="validation_plan",
        status="in_progress", parent_task_id="main-1", validation_task=candidate("v1", 1).task,
        experiment_info=ExperimentInfo(current_experiment="重复运行"),
    )
    repository.commit(stored, repository.list_events("s1")[-1].model_copy(update={"event_id": "seed-validation"}))
    model.enqueue(
        "working_qa",
        WorkingQAOutput(action="report_plan_issue", reason="验证失败", reply="不应绕过记录"),
    )
    with pytest.raises(InvariantViolationError):
        orchestrator.run_working_qa("s1", "验证失败")


def test_validation_queue_selects_by_rank_and_preserves_skip_reasons(completion_bundle):
    orchestrator, model, repository = completion_bundle
    propose_success(orchestrator, model)
    orchestrator.record_main_result("s1", main_result())
    output = CompleteAgentOutput(
        mode="validation", plan=None, final_hint="需要验证",
        validation_candidates=[candidate("v2", 2), candidate("v1", 1)],
    )
    model.enqueue("complete", output)
    orchestrator.run_complete("s1", completion_status=False)
    assert [item.candidate_id for item in repository.get("s1").validation_queue.offered] == ["v1", "v2"]

    selected = orchestrator.select_validations(
        "s1",
        ValidationSelection(selected_candidate_ids=["v2"], skipped_candidate_ids=["v1"], user_reason="没有 GPU"),
    )
    assert selected.phase is SessionPhase.WORKING
    assert selected.current_task.validation_task == candidate("v2", 2).task
    skipped = selected.validation_queue.skipped[0]
    assert skipped.mentor_rationale == "导师理由 v1"
    assert skipped.user_reason == "没有 GPU"


def test_existing_pending_validation_precedes_new_complete_candidates(completion_bundle):
    orchestrator, model, repository = completion_bundle
    propose_success(orchestrator, model)
    orchestrator.record_main_result("s1", main_result())
    model.enqueue(
        "complete",
        CompleteAgentOutput(
            mode="validation", plan=None, final_hint="先做两项",
            validation_candidates=[candidate("v2", 2), candidate("v1", 1)],
        ),
    )
    orchestrator.run_complete("s1", completion_status=False)
    orchestrator.select_validations(
        "s1", ValidationSelection(selected_candidate_ids=["v2", "v1"])
    )
    model.enqueue(
        "working_qa",
        WorkingQAOutput(
            action="success", reason="验证完成", reply="",
            updated_experiment_info=ExperimentInfo(
                current_experiment=candidate("v1", 1).task.name,
                actual_result="结论稳定",
            ),
        ),
    )
    orchestrator.run_working_qa("s1", "完成了吗？")
    orchestrator.record_validation_result(
        "s1",
        ValidationResult(
            task=candidate("v1", 1).task, actual_result="结论稳定",
            conclusion="支持复现", is_success=True,
            execution_status="completed", impact="supports",
        ),
    )
    complete_calls = len([call for call in model.calls if call.agent_name == "complete"])

    orchestrator.run_complete("s1", completion_status=False)

    stored = repository.get("s1")
    assert stored.phase is SessionPhase.WORKING
    assert stored.current_task.validation_task == candidate("v2", 2).task
    assert len([call for call in model.calls if call.agent_name == "complete"]) == complete_calls


def test_completed_candidate_is_not_reoffered(completion_bundle):
    orchestrator, model, repository = completion_bundle
    propose_success(orchestrator, model)
    orchestrator.record_main_result("s1", main_result())
    model.enqueue(
        "complete",
        CompleteAgentOutput(
            mode="validation", plan=None, final_hint="先验证",
            validation_candidates=[candidate("v1", 1)],
        ),
    )
    orchestrator.run_complete("s1", completion_status=False)
    orchestrator.select_validations(
        "s1", ValidationSelection(selected_candidate_ids=["v1"])
    )
    stored = repository.get("s1")
    stored.phase = SessionPhase.AWAITING_RESULT_RECORD
    repository.commit(
        stored,
        repository.list_events("s1")[-1].model_copy(update={"event_id": "seed-v1-result"}),
    )
    orchestrator.record_validation_result(
        "s1",
        ValidationResult(
            task=candidate("v1", 1).task, actual_result="已完成",
            conclusion="已检查", is_success=True,
            execution_status="completed", impact="supports",
        ),
    )
    model.enqueue(
        "complete",
        CompleteAgentOutput(
            mode="validation", plan=None, final_hint="追加验证",
            validation_candidates=[candidate("v1", 1), candidate("v3", 3)],
        ),
    )

    orchestrator.run_complete("s1", completion_status=False)

    queue = repository.get("s1").validation_queue
    assert [item.candidate_id for item in queue.offered] == ["v3"]
    assert [item.candidate.candidate_id for item in queue.selected] == ["v1"]
    assert queue.selected[0].status == "completed"


@pytest.mark.parametrize(
    ("execution_status", "impact", "failure_reason"),
    [("completed", "supports", None), ("completed", "contradicts", None), ("failed", "neutral", "进程退出")],
)
def test_validation_results_preserve_outcome_and_return_completing(
    completion_bundle, execution_status, impact, failure_reason
):
    orchestrator, _, repository = completion_bundle
    stored = repository.get("s1")
    stored.phase = SessionPhase.AWAITING_RESULT_RECORD
    stored.main_experiment = main_result()
    task = candidate("v1", 1).task
    stored.current_task = ExperimentTaskContext(
        task_id="v-task", task_kind="validation", origin="validation_plan",
        status="in_progress", parent_task_id="main-1", validation_task=task,
        experiment_info=ExperimentInfo(current_experiment=task.name),
    )
    repository.commit(stored, repository.list_events("s1")[-1].model_copy(update={"event_id": "seed-result"}))
    result = ValidationResult(
        task=task, actual_result="如实记录", conclusion="按影响解释", is_success=False,
        execution_status=execution_status, impact=impact, failure_reason=failure_reason,
    )
    returned = orchestrator.record_validation_result("s1", result)
    assert returned.phase is SessionPhase.COMPLETING
    assert returned.current_task.status == "completed"
    assert returned.completed_validations[-1] == result


def test_validation_result_must_match_current_task(completion_bundle):
    orchestrator, _, repository = completion_bundle
    stored = repository.get("s1")
    stored.phase = SessionPhase.AWAITING_RESULT_RECORD
    stored.main_experiment = main_result()
    active = candidate("v1", 1).task
    stored.current_task = ExperimentTaskContext(
        task_id="v-task", task_kind="validation", origin="validation_plan",
        status="in_progress", parent_task_id="main-1", validation_task=active,
        experiment_info=ExperimentInfo(current_experiment=active.name),
    )
    repository.commit(stored, repository.list_events("s1")[-1].model_copy(update={"event_id": "seed-mismatch"}))
    before = repository.get("s1")

    with pytest.raises(InvariantViolationError):
        orchestrator.record_validation_result(
            "s1",
            ValidationResult(
                task=candidate("v2", 2).task, actual_result="另一项结果",
                conclusion="不属于当前任务", is_success=False,
                execution_status="completed", impact="neutral",
            ),
        )

    assert repository.get("s1") == before


def test_plan_revision_decisions_preserve_results(completion_bundle):
    orchestrator, _, repository = completion_bundle
    stored = repository.get("s1")
    stored.phase = SessionPhase.AWAITING_PLAN_REVISION_DECISION
    stored.main_experiment = main_result()
    stored.latest_complete_output = CompleteAgentOutput(
        mode="plan_revision", plan=None, final_hint="需要重估", revision_reason="负面结果动摇主张"
    )
    repository.commit(stored, repository.list_events("s1")[-1].model_copy(update={"event_id": "seed-revision"}))

    continued = orchestrator.decide_plan_revision("s1", "continue_with_warning", user_reason="接受风险")
    assert continued.phase is SessionPhase.COMPLETING
    assert continued.plan_revision_records[-1].mentor_reason == "负面结果动摇主张"
    assert continued.plan_revision_records[-1].user_reason == "接受风险"
    assert continued.main_experiment == main_result()


def test_plan_revision_revise_resets_round_without_erasing_facts(completion_bundle):
    orchestrator, _, repository = completion_bundle
    stored = repository.get("s1")
    stored.phase = SessionPhase.AWAITING_PLAN_REVISION_DECISION
    stored.main_experiment = main_result()
    stored.check_round = 4
    repository.commit(stored, repository.list_events("s1")[-1].model_copy(update={"event_id": "seed-revise"}))
    revised = orchestrator.decide_plan_revision("s1", "revise", user_reason="调整假设")
    assert revised.phase is SessionPhase.PLANNING
    assert revised.check_round == 0
    assert revised.main_experiment == main_result()


def test_plan_revision_end_project_keeps_negative_result(completion_bundle):
    orchestrator, _, repository = completion_bundle
    stored = repository.get("s1")
    stored.phase = SessionPhase.AWAITING_PLAN_REVISION_DECISION
    stored.main_experiment = main_result()
    repository.commit(stored, repository.list_events("s1")[-1].model_copy(update={"event_id": "seed-end"}))
    ended = orchestrator.decide_plan_revision("s1", "end_project", user_reason="结论已足够")
    assert ended.phase is SessionPhase.COMPLETED
    assert ended.main_experiment == main_result()
