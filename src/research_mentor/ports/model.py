"""Generic async structured-model boundary."""

from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from research_mentor.domain.jobs import AgentName


OutputT = TypeVar("OutputT", bound=BaseModel)


class ModelRequest(BaseModel, Generic[OutputT]):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent_name: AgentName
    model_profile: str
    instructions: str
    user_input: str
    output_model: type[OutputT]
    timeout: float = Field(gt=0.0)
    trace_id: str


class StructuredModelPort(Protocol):
    async def generate(self, request: ModelRequest[OutputT]) -> OutputT: ...
