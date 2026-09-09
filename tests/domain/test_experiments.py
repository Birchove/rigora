from typing import get_args

import pytest
from pydantic import ValidationError

from research_mentor.domain.experiments import (
    ExperimentInfo,
    ExperimentTaskContext,
    MainExperimentResult,
    ExecutionStatus,
    ResultImpact,
    ValidationTask,
)


def validation_task() -> ValidationTask:
    return ValidationTask(
        name="benchmark",
        purpose="compare performance",
        method="run benchmark",
        evaluation_criteria=["记录准确率与耗时"],
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"parent_task_id": "parent-1"},
        {"validation_task": validation_task()},
    ],
)
def test_main_task_rejects_parent_or_validation_task(extra):
    with pytest.raises(ValidationError):
        ExperimentTaskContext(
            task_id="main-1",
            task_kind="main",
            origin="plan",
            status="pending",
            **extra,
        )


def test_validation_task_requires_parent_id_and_validation_task():
    with pytest.raises(ValidationError):
        ExperimentTaskContext(
            task_id="validation-1",
            task_kind="validation",
            origin="validation_plan",
            status="pending",
            validation_task=validation_task(),
        )
    with pytest.raises(ValidationError):
        ExperimentTaskContext(
            task_id="validation-2",
            task_kind="validation",
            origin="validation_plan",
            status="pending",
            parent_task_id="main-1",
        )


def test_completed_main_result_can_record_negative_actual_result():
    result = MainExperimentResult(
        objective="test hypothesis",
        method="run experiment",
        actual_result="hypothesis not supported",
        conclusion="revise hypothesis",
        execution_status="completed",
        impact="contradicts",
    )
    context = ExperimentTaskContext(
        task_id="main-1",
        task_kind="main",
        origin="plan",
        status="completed",
        experiment_info=ExperimentInfo(actual_result=result.actual_result),
    )
    assert context.status == "completed"
    assert context.experiment_info.actual_result == "hypothesis not supported"


def test_negative_scientific_finding_is_completed_execution() -> None:
    result = MainExperimentResult(
        objective="比较延迟",
        method="基准测试",
        actual_result="尾延迟升高",
        conclusion="不支持预期",
        execution_status="completed",
        impact="contradicts",
    )

    assert result.failure_reason is None


def test_result_enums_are_exact() -> None:
    assert set(get_args(ResultImpact)) == {
        "supports",
        "neutral",
        "contradicts",
        "invalidates",
    }
    assert set(get_args(ExecutionStatus)) == {"completed", "failed", "cancelled"}


def test_valid_main_and_validation_contexts_are_accepted():
    main = ExperimentTaskContext(
        task_id="main-1", task_kind="main", origin="forward", status="in_progress"
    )
    validation = ExperimentTaskContext(
        task_id="validation-1",
        task_kind="validation",
        origin="validation_plan",
        status="pending",
        parent_task_id="main-1",
        validation_task=validation_task(),
    )
    assert main.parent_task_id is None
    assert validation.validation_task is not None


def test_default_factory_values_are_not_shared():
    first = ExperimentInfo()
    second = ExperimentInfo()
    first.observations.append("observation")
    assert second.observations == []


def test_validation_task_uses_domain_neutral_structure() -> None:
    task = ValidationTask(
        name="高峰订单下的路径拥堵实验",
        purpose="验证效率提升是否只在低负载下成立",
        method="逐级提高订单到达率并记录完成时间",
        evaluation_criteria=["平均完成时间", "最长等待时间"],
        expected_result="高负载下仍优于现有方案",
    )

    assert task.model_dump() == {
        "name": "高峰订单下的路径拥堵实验",
        "purpose": "验证效率提升是否只在低负载下成立",
        "method": "逐级提高订单到达率并记录完成时间",
        "evaluation_criteria": ["平均完成时间", "最长等待时间"],
        "expected_result": "高负载下仍优于现有方案",
    }


def test_legacy_validation_task_ignores_old_classification_fields() -> None:
    task = ValidationTask(
        paradigm="effectiveness",
        validation_type="benchmarking",
        name="旧实验",
        purpose="读取历史项目",
        method="沿用历史方法",
    )

    assert task.evaluation_criteria == []
    assert "paradigm" not in task.model_dump()
    assert "validation_type" not in task.model_dump()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_kind", "invalid"),
        ("origin", "invalid"),
        ("status", "invalid"),
    ],
)
def test_experiment_task_context_enum_values_are_rejected(field, value):
    payload = {
        "task_id": "main-1",
        "task_kind": "main",
        "origin": "plan",
        "status": "pending",
    }
    payload[field] = value
    with pytest.raises(ValidationError):
        ExperimentTaskContext(**payload)
