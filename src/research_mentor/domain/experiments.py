from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator


class ExperimentInfo(BaseModel):
    current_experiment: str | None = None
    expected_result: str | None = None
    actual_result: str | None = None
    observations: list[str] = Field(default_factory=list)


ExperimentTaskKind = Literal["main", "validation"]
ExperimentTaskOrigin = Literal["plan", "forward", "validation_plan"]
ExperimentTaskStatus = Literal[
    "pending", "in_progress", "completed", "blocked", "cancelled"
]
ResultImpact = Literal["supports", "neutral", "contradicts", "invalidates"]
ExecutionStatus = Literal["completed", "failed", "cancelled"]


class _ExperimentResult(BaseModel):
    execution_status: ExecutionStatus
    impact: ResultImpact
    failure_reason: str | None = None

    @model_validator(mode="after")
    def validate_execution_result(self) -> Self:
        if self.execution_status == "completed" and self.failure_reason is not None:
            raise ValueError("completed execution cannot include failure_reason")
        if self.execution_status != "completed":
            if self.failure_reason is None or not self.failure_reason.strip():
                raise ValueError("failed or cancelled execution requires failure_reason")
        return self


class ValidationTask(BaseModel):
    name: str
    purpose: str
    # ponytail: schema 只拦空白（min_length=1 保旧 JSON 兼容），method 长度与质量由 Complete Prompt 约束
    method: Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
    evaluation_criteria: list[str] = Field(default_factory=list)
    expected_result: str | None = None
    required_conditions: list[str] = Field(default_factory=list)


class ValidationResult(_ExperimentResult):
    task: ValidationTask
    actual_result: str
    conclusion: str
    is_success: bool
    evidence_files: list[str] = Field(default_factory=list)


class MainExperimentResult(_ExperimentResult):
    objective: str
    method: str
    expected_result: str | None = None
    actual_result: str
    conclusion: str
    evidence_files: list[str] = Field(default_factory=list)


class ExperimentTaskContext(BaseModel):
    task_id: str
    task_kind: ExperimentTaskKind
    origin: ExperimentTaskOrigin
    status: ExperimentTaskStatus
    parent_task_id: str | None = None
    validation_task: ValidationTask | None = None
    experiment_info: ExperimentInfo = Field(default_factory=ExperimentInfo)

    @model_validator(mode="after")
    def validate_task_relationships(self) -> "ExperimentTaskContext":
        if self.task_kind == "main":
            if self.parent_task_id is not None or self.validation_task is not None:
                raise ValueError("main tasks cannot have parent_task_id or validation_task")
        elif self.parent_task_id is None or self.validation_task is None:
            raise ValueError(
                "validation tasks require parent_task_id and validation_task"
            )
        return self
