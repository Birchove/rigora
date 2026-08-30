"""Structured model port."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

from research_mentor.agents.common import AgentName

OutputT = TypeVar("OutputT", bound=BaseModel)


class StructuredModelPort(Protocol):
    def invoke(self, *, agent_name: AgentName, instructions: str, user_input: str, output_model: type[OutputT]) -> OutputT:
        raise NotImplementedError
