"""Runner for the Complete Agent."""

from pydantic import BaseModel

from research_mentor.agents.complete.contracts import CompleteAgentInput, CompleteAgentOutput
from research_mentor.agents.complete.prompting import build_complete_invocation
from research_mentor.ports.model import StructuredModelPort


class CompleteRunner:
    def __init__(self, model: StructuredModelPort) -> None:
        self._model = model

    def run(self, request: CompleteAgentInput) -> CompleteAgentOutput:
        invocation = build_complete_invocation(request)
        result = self._model.invoke(
            agent_name=invocation.agent_name,
            instructions=invocation.instructions,
            user_input=invocation.user_input,
            output_model=invocation.output_model,
        )
        if isinstance(result, BaseModel):
            result = result.model_dump(mode="python", warnings=False)
        return CompleteAgentOutput.model_validate(result)
