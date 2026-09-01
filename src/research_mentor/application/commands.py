"""Typed mutation commands and application results."""

from typing import Annotated, Literal, TypeAlias, get_args

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from research_mentor.domain.completion import ValidationSelection
from research_mentor.domain.experiments import MainExperimentResult, ValidationResult
from research_mentor.domain.research import (
    InitialInput,
    NonBlankText,
    PlanGenerationMode,
    UserPlanDecision,
)
from research_mentor.harness.phase import SessionPhase


class CommandBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    expected_version: int = Field(ge=1)


class SubmitIdeaCommand(CommandBase):
    type: Literal["submit_idea"] = "submit_idea"
    idea: InitialInput


class SubmitRefinementCommand(CommandBase):
    type: Literal["submit_refinement"] = "submit_refinement"
    refinement: str = Field(min_length=1)


class RunPlanCommand(CommandBase):
    type: Literal["run_plan"] = "run_plan"
    mode: PlanGenerationMode = "low"


class RunCheckCommand(CommandBase):
    type: Literal["run_check"] = "run_check"
    candidate_id: str | None = None


class ContinueImperfectPlanDecision(BaseModel):
    decision: Literal["continue_imperfect"]
    user_reason: NonBlankText


PlanDecisionPayload: TypeAlias = Annotated[
    UserPlanDecision | ContinueImperfectPlanDecision,
    Field(discriminator="decision"),
]


class DecidePlanCommand(CommandBase):
    type: Literal["decide_plan"] = "decide_plan"
    decision: PlanDecisionPayload
    candidate_id: str | None = None


class SendWorkingMessageCommand(CommandBase):
    type: Literal["send_working_message"] = "send_working_message"
    question: str = Field(min_length=1)


class ResumeWorkingCommand(CommandBase):
    type: Literal["resume_working"] = "resume_working"


class RecordMainResultCommand(CommandBase):
    type: Literal["record_main_result"] = "record_main_result"
    result: MainExperimentResult


class RecordValidationResultCommand(CommandBase):
    type: Literal["record_validation_result"] = "record_validation_result"
    result: ValidationResult


class RunCompleteCommand(CommandBase):
    type: Literal["run_complete"] = "run_complete"


class SelectValidationsCommand(CommandBase):
    type: Literal["select_validations"] = "select_validations"
    selection: ValidationSelection


class DecidePlanRevisionCommand(CommandBase):
    type: Literal["decide_plan_revision"] = "decide_plan_revision"
    decision: Literal["revise", "continue_with_warning", "end_project"]
    user_reason: str | None = None


class CancelRunCommand(CommandBase):
    type: Literal["cancel_run"] = "cancel_run"
    run_id: str | None = None


class RestartResearchCommand(CommandBase):
    type: Literal["restart_research"] = "restart_research"
    confirm_restart: Literal[True]
    idea: InitialInput


class ArchiveProjectCommand(CommandBase):
    type: Literal["archive_project"] = "archive_project"


Command: TypeAlias = Annotated[
    SubmitIdeaCommand
    | SubmitRefinementCommand
    | RunPlanCommand
    | RunCheckCommand
    | DecidePlanCommand
    | SendWorkingMessageCommand
    | ResumeWorkingCommand
    | RecordMainResultCommand
    | RecordValidationResultCommand
    | RunCompleteCommand
    | SelectValidationsCommand
    | DecidePlanRevisionCommand
    | CancelRunCommand
    | RestartResearchCommand
    | ArchiveProjectCommand,
    Field(discriminator="type"),
]


def command_type_names() -> set[str]:
    union = get_args(Command)[0]
    return {
        get_args(command_type.model_fields["type"].annotation)[0]
        for command_type in get_args(union)
    }


class AgentCommandReceipt(BaseModel):
    result_kind: Literal["agent"] = "agent"
    project_id: str
    command_id: str
    run_id: str


class DeterministicCommandResult(BaseModel):
    result_kind: Literal["deterministic"] = "deterministic"
    project_id: str
    command_id: str
    session_id: str
    version: int = Field(ge=1)
    phase: SessionPhase
    payload: dict[str, JsonValue] = Field(default_factory=dict)


CommandResult: TypeAlias = Annotated[
    AgentCommandReceipt | DeterministicCommandResult,
    Field(discriminator="result_kind"),
]
