"""Runner for the Plan Loop Agent."""

import asyncio

from pydantic import BaseModel

from research_mentor.agents.plan_loop.contracts import PlanLoopInput, PlanLoopOutput
from research_mentor.agents.plan_loop.prompting import build_plan_loop_invocation
from research_mentor.ports.model import ModelRequest, StructuredModelPort


class PlanLoopRunner:
    def __init__(self, model: StructuredModelPort) -> None:
        self._model = model

    async def run(
        self,
        request: PlanLoopInput,
        *,
        model_profile: str = "default",
        timeout: float = 30.0,
        trace_id: str = "local",
    ) -> PlanLoopOutput:
        invocation = build_plan_loop_invocation(request)
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
        return PlanLoopOutput.model_validate(result)

    def run_sync(self, request: PlanLoopInput) -> PlanLoopOutput:
        return asyncio.run(self.run(request))
