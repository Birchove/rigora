"""Scripted async structured-model adapters for tests and demo mode."""

from collections import defaultdict, deque
from collections.abc import Iterable

from pydantic import BaseModel, JsonValue, ValidationError

from research_mentor.domain.jobs import AgentName
from research_mentor.errors import ModelOutputInvalid, PortExecutionError
from research_mentor.ports.model import ModelRequest, OutputT

ScriptedOutput = BaseModel | dict[str, JsonValue]


def _validate_output(
    request: ModelRequest[OutputT],
    output: ScriptedOutput,
) -> OutputT:
    payload = (
        output.model_dump(mode="python", warnings=False)
        if isinstance(output, BaseModel)
        else output
    )
    try:
        return request.output_model.model_validate(payload)
    except ValidationError as exc:
        raise ModelOutputInvalid(errors=exc.errors()) from exc


class ScriptedStructuredModel:
    def __init__(self, responses: Iterable[ScriptedOutput]) -> None:
        self._responses = deque(responses)
        self.requests: list[ModelRequest[BaseModel]] = []

    async def generate(self, request: ModelRequest[OutputT]) -> OutputT:
        self.requests.append(request.model_copy(deep=True))
        if not self._responses:
            raise PortExecutionError("No scripted model response remains")
        return _validate_output(request, self._responses.popleft())


class MemoryModelAdapter:
    def __init__(self) -> None:
        self._queues: dict[AgentName, deque[ScriptedOutput]] = defaultdict(deque)
        self.requests: list[ModelRequest[BaseModel]] = []

    def enqueue(self, agent_name: AgentName, result: ScriptedOutput) -> None:
        self._queues[agent_name].append(result)

    async def generate(self, request: ModelRequest[OutputT]) -> OutputT:
        self.requests.append(request.model_copy(deep=True))
        queue = self._queues[request.agent_name]
        if not queue:
            raise PortExecutionError(
                f"No queued result for agent: {request.agent_name}"
            )
        return _validate_output(request, queue.popleft())
