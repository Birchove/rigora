"""Deterministic construction of experiment task records."""

from uuid import uuid4

from research_mentor.domain.experiments import (
    ExperimentInfo,
    ExperimentTaskContext,
    ExperimentTaskOrigin,
    ValidationTask,
)


class TaskFactory:
    """Create task records with Harness-owned IDs and initial status."""

    @staticmethod
    def create_main(
        *,
        origin: ExperimentTaskOrigin,
        current_experiment: str | None = None,
        expected_result: str | None = None,
    ) -> ExperimentTaskContext:
        return ExperimentTaskContext(
            task_id=str(uuid4()),
            task_kind="main",
            origin=origin,
            status="pending",
            experiment_info=ExperimentInfo(
                current_experiment=current_experiment,
                expected_result=expected_result,
            ),
        )

    @staticmethod
    def create_validation(
        *,
        parent_task_id: str,
        task: ValidationTask,
    ) -> ExperimentTaskContext:
        return ExperimentTaskContext(
            task_id=str(uuid4()),
            task_kind="validation",
            origin="validation_plan",
            status="pending",
            parent_task_id=parent_task_id,
            validation_task=task.model_copy(deep=True),
            experiment_info=ExperimentInfo(
                current_experiment=task.name,
                expected_result=task.expected_result,
            ),
        )
