"""Runner for the Plan Loop Agent."""

from pydantic import BaseModel

from research_mentor.agents.plan_loop.contracts import PlanLoopInput, PlanLoopOutput
from research_mentor.agents.plan_loop.prompting import build_plan_loop_invocation
from research_mentor.ports.model import StructuredModelPort


class PlanLoopRunner:
    def __init__(self, model: StructuredModelPort) -> None:
        self._model = model

    def run(self, request: PlanLoopInput) -> PlanLoopOutput:
        invocation = build_plan_loop_invocation(request)
        result = self._model.invoke(
            agent_name=invocation.agent_name,
            instructions=invocation.instructions,
            user_input=invocation.user_input,
            output_model=invocation.output_model,
        )
        if isinstance(result, BaseModel):
            result = result.model_dump(mode="python", warnings=False)
        return PlanLoopOutput.model_validate(result)
