"""Runner for the Complete Agent."""

import asyncio

from pydantic import BaseModel

from research_mentor.agents.complete.contracts import CompleteAgentInput, CompleteAgentOutput
from research_mentor.agents.complete.prompting import build_complete_invocation
from research_mentor.hyperparameters import MODEL_REQUEST_TIMEOUT_SECONDS
from research_mentor.ports.model import ModelRequest, StructuredModelPort


class CompleteRunner:
    def __init__(self, model: StructuredModelPort) -> None:
        self._model = model

    async def run(
        self,
        request: CompleteAgentInput,
        *,
        model_profile: str = "default",
        timeout: float = MODEL_REQUEST_TIMEOUT_SECONDS,
        trace_id: str = "local",
    ) -> CompleteAgentOutput:
        invocation = build_complete_invocation(request)
        result = await self._model.generate(
            ModelRequest(
                agent_name=invocation.agent_name,
                model_profile=model_profile,
                instructions=invocation.instructions,
                user_input=invocation.user_input,
                output_model=invocation.output_model,
                timeout=timeout,
                trace_id=trace_id,
            )
        )
        if isinstance(result, BaseModel):
            result = result.model_dump(mode="python", warnings=False)
        return CompleteAgentOutput.model_validate(result)

    def run_sync(self, request: CompleteAgentInput) -> CompleteAgentOutput:
        return asyncio.run(self.run(request))
