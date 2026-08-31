"""Agent run domain models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

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
