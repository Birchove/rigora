import pytest

from research_mentor.application.allowed_commands import (
    allowed_commands,
    assert_allowed,
)
from research_mentor.errors import IllegalTransitionError
from research_mentor.harness.phase import SessionPhase
from research_mentor.harness.state import ResearchSession
from research_mentor.harness.session_slices import PendingWorkingClarification
from research_mentor.domain.experiments import ExperimentTaskContext, ValidationTask


def session_with_current_task(task_kind: str) -> ResearchSession:
    validation_task = None
    if task_kind == "validation":
        validation_task = ValidationTask(
            paradigm="effectiveness",
            validation_type="ablation",
            name="消融",
            purpose="验证组件贡献",
            method="移除组件后对比",
        )
    return ResearchSession(
        session_id="s1",
        phase=SessionPhase.AWAITING_RESULT_RECORD,
        current_task=ExperimentTaskContext(
            task_id="task-1",
            task_kind=task_kind,
            origin="plan" if task_kind == "main" else "validation_plan",
            status="in_progress",
            parent_task_id=None if task_kind == "main" else "main-1",
            validation_task=validation_task,
        ),
    )


def test_result_phase_exposes_only_matching_record_command() -> None:
    main = session_with_current_task("main")
    validation = session_with_current_task("validation")
    assert allowed_commands(main) == (
        "record_main_result",
        "resume_working",
        "cancel_run",
        "restart_research",
        "archive_project",
    )
    assert allowed_commands(validation) == (
        "record_validation_result",
        "resume_working",
        "cancel_run",
        "restart_research",
        "archive_project",
    )


@pytest.mark.parametrize(
    ("phase", "expected_primary"),
    [
        (SessionPhase.AWAITING_IDEA, "submit_idea"),
        (SessionPhase.AWAITING_IDEA_REFINEMENT, "submit_refinement"),
        (SessionPhase.PLANNING, "run_plan"),
        (SessionPhase.CHECKING_KEY_INSIGHT, "run_check"),
        (SessionPhase.AWAITING_PLAN_DECISION, "decide_plan"),
        (SessionPhase.WORKING, "send_working_message"),
        (SessionPhase.COMPLETING, "run_complete"),
        (SessionPhase.AWAITING_VALIDATION_SELECTION, "select_validations"),
        (SessionPhase.AWAITING_PLAN_REVISION_DECISION, "decide_plan_revision"),
        (SessionPhase.CHECK_LOOP_EXHAUSTED, "decide_plan"),
    ],
)
def test_phase_exposes_its_harness_entrypoint(
    phase: SessionPhase, expected_primary: str
) -> None:
    commands = allowed_commands(ResearchSession(session_id="s1", phase=phase))

    assert commands[0] == expected_primary
    assert "restart_research" in commands
    assert "archive_project" in commands
    if phase is SessionPhase.WORKING:
        assert "finish_working" in commands


def test_working_clarification_replaces_composer_command() -> None:
    session = ResearchSession(
        session_id="s1",
        phase=SessionPhase.WORKING,
        pending_working_clarification=PendingWorkingClarification(
            original_question="exact-match 掉了 3 个点是什么原因？",
            clarify_reply="请补充是否已有 actual_result。",
        ),
    )
    commands = allowed_commands(session)

    assert commands[0] == "submit_working_clarification"
    assert "send_working_message" not in commands
    assert "finish_working" in commands
    with pytest.raises(IllegalTransitionError):
        assert_allowed("send_working_message", session)


def test_illegal_phase_is_rejected_by_server_authority() -> None:
    session = ResearchSession(session_id="s1", phase=SessionPhase.COMPLETED)

    with pytest.raises(IllegalTransitionError):
        assert_allowed("run_plan", session)


def test_legacy_working_context_phase_does_not_expose_invalid_agent_command() -> None:
    session = ResearchSession(
        session_id="s1", phase=SessionPhase.AWAITING_WORKING_CONTEXT
    )

    assert allowed_commands(session) == (
        "cancel_run",
        "restart_research",
        "archive_project",
    )
