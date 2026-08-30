from typing import Literal

from pydantic import BaseModel, Field, model_validator


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
ValidationParadigm = Literal[
    "effectiveness",
    "efficiency",
    "robustness_reliability",
    "theory_interpretability",
    "engineering_human_factors",
    "meta_statistical",
]
ValidationType = Literal[
    "benchmarking",
    "ablation",
    "baseline_comparison",
    "generalization",
    "throughput_latency",
    "resource_consumption",
    "scalability",
    "energy_efficiency",
    "adversarial",
    "ood_detection",
    "stress_test",
    "long_tail_few_shot",
    "convergence",
    "feature_visualization",
    "case_study_error_analysis",
    "developer_productivity",
    "user_study_ab_test",
    "regression_testing",
    "multiple_runs",
    "significance_test",
]


class ValidationTask(BaseModel):
    paradigm: ValidationParadigm
    validation_type: ValidationType
    name: str
    purpose: str
    method: str
    expected_result: str | None = None


class ValidationResult(BaseModel):
    task: ValidationTask
    actual_result: str
    conclusion: str
    is_success: bool
    evidence_files: list[str] = Field(default_factory=list)


class MainExperimentResult(BaseModel):
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
