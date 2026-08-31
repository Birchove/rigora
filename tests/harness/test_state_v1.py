import pytest
from pydantic import ValidationError

from research_mentor.domain.checks import CheckRound
from research_mentor.domain.experiments import ValidationTask
from research_mentor.harness.state import SessionPhase
from research_mentor.harness.task_factory import TaskFactory


def test_session_phase_values_are_exact() -> None:
    assert {phase.value for phase in SessionPhase} == {
        "awaiting_idea",
        "awaiting_idea_refinement",
        "planning",
        "checking_key_insight",
        "awaiting_plan_decision",
        "awaiting_working_context",
        "working",
        "awaiting_result_record",
        "completing",
        "awaiting_validation_selection",
        "awaiting_plan_revision_decision",
        "completed",
        "rejected",
        "check_loop_exhausted",
    }


def test_check_round_records_harness_authority(check_output) -> None:
    record = CheckRound(
        check_round=1,
        output=check_output,
        final_score=6.0,
        passed=True,
    )

    assert record.check_round == 1
    assert record.final_score == 6.0
    assert record.passed is True

    with pytest.raises(ValidationError):
        CheckRound(
            check_round=0,
            output=check_output,
            final_score=6.0,
            passed=True,
        )


def test_task_factory_owns_ids_status_and_defaults() -> None:
    first = TaskFactory.create_main(origin="plan")
    second = TaskFactory.create_main(origin="forward", current_experiment="复现实验")

    assert first.task_id != second.task_id
    assert first.status == second.status == "pending"
    assert first.experiment_info.current_experiment is None
    assert second.experiment_info.current_experiment == "复现实验"


def test_task_factory_creates_valid_validation_relationship() -> None:
    parent = TaskFactory.create_main(origin="plan")
    task = ValidationTask(
        paradigm="effectiveness",
        validation_type="ablation",
        name="消融实验",
        purpose="验证模块贡献",
        method="逐一移除模块",
    )

    validation = TaskFactory.create_validation(parent_task_id=parent.task_id, task=task)

    assert validation.task_kind == "validation"
    assert validation.origin == "validation_plan"
    assert validation.status == "pending"
    assert validation.parent_task_id == parent.task_id
    assert validation.validation_task == task
