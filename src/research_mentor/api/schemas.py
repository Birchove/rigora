"""Stable HTTP request and response schemas."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from research_mentor.application.views import ProjectView
from research_mentor.hyperparameters import DOMAIN_MAX_LENGTH, PROJECT_TITLE_MAX_LENGTH


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=PROJECT_TITLE_MAX_LENGTH)
    domain: str = Field(min_length=1, max_length=DOMAIN_MAX_LENGTH)


class AgentCommandResponse(BaseModel):
    command_id: str
    run_id: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
