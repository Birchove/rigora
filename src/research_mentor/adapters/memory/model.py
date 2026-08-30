"""In-memory structured model adapter."""

from collections import defaultdict, deque

from pydantic import BaseModel, JsonValue

from research_mentor.agents.common import AgentName
from research_mentor.errors import PortExecutionError
from research_mentor.ports.model import OutputT


class MemoryModelAdapter:
    def __init__(self) -> None:
        self._queues: dict[AgentName, deque[BaseModel | dict[str, JsonValue]]] = defaultdict(deque)

    def enqueue(self, agent_name: AgentName, result: BaseModel | dict[str, JsonValue]) -> None:
        self._queues[agent_name].append(result)

    def invoke(self, *, agent_name: AgentName, instructions: str, user_input: str, output_model: type[OutputT]) -> OutputT:
        queue = self._queues[agent_name]
        if not queue:
            raise PortExecutionError(f"No queued result for agent: {agent_name}")
        return output_model.model_validate(queue.popleft())
