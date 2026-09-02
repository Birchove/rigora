"""Agent run domain models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, JsonValue

from research_mentor.hyperparameters import run_config_snapshot

AgentName = Literal["idea_review", "plan_loop", "key_insight_check", "working_qa", "complete"]
AgentRunStatus = Literal[
    "queued", "running", "succeeded", "failed", "timed_out", "cancelled"
]


class AgentRun(BaseModel):
    run_id: str
    project_id: str
    command_id: str
    agent_name: AgentName
    status: AgentRunStatus
    attempt: int = Field(ge=0)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    public_message: str | None = None
    error_code: str | None = None
    # Durable queue metadata. These fields are persistence/application details;
    # public API views should project only the fields above.
    available_at: datetime | None = None
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    row_version: int = Field(default=1, ge=1)
    cancel_requested: bool = False
    input_snapshot: dict[str, JsonValue] = Field(default_factory=dict)
    config_snapshot: dict[str, JsonValue] = Field(default_factory=run_config_snapshot)
