"""Runner for the Working QA Agent."""

from pydantic import BaseModel

from research_mentor.agents.working_qa.contracts import WorkingQAInput, WorkingQAOutput
from research_mentor.agents.working_qa.prompting import build_working_qa_invocation
from research_mentor.hyperparameters import MODEL_REQUEST_TIMEOUT_SECONDS
from research_mentor.ports.model import ModelRequest, StructuredModelPort
from research_mentor.runtime_async import run_coro_sync


class WorkingQARunner:
    def __init__(self, model: StructuredModelPort) -> None:
        self._model = model

    async def run(
        self,
        request: WorkingQAInput,
        *,
        model_profile: str = "default",
        timeout: float = MODEL_REQUEST_TIMEOUT_SECONDS,
        trace_id: str = "local",
    ) -> WorkingQAOutput:
        invocation = build_working_qa_invocation(request)
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
        return WorkingQAOutput.model_validate(result)

    def run_sync(
        self, request: WorkingQAInput, *, model_profile: str = "default"
    ) -> WorkingQAOutput:
        return run_coro_sync(self.run(request, model_profile=model_profile))
