"""Conversation domain models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from research_mentor.domain.jobs import AgentName


class ConversationTurn(BaseModel):
    turn_id: str
    role: Literal["user", "assistant", "system_event"]
    content: str
    created_at: datetime
    agent_name: AgentName | None = None
    evidence_ids: list[str] = Field(default_factory=list)
