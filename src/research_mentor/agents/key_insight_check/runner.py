"""Runner for the Key Insight Check Agent."""

from pydantic import BaseModel

from research_mentor.agents.key_insight_check.contracts import (
    KeyInsightAssessment,
    KeyInsightCheckInput,
)
from research_mentor.agents.key_insight_check.prompting import (
    build_key_insight_check_invocation,
)
from research_mentor.hyperparameters import MODEL_REQUEST_TIMEOUT_SECONDS
from research_mentor.ports.model import ModelRequest, StructuredModelPort
from research_mentor.runtime_async import run_coro_sync


class KeyInsightCheckRunner:
    def __init__(self, model: StructuredModelPort) -> None:
        self._model = model

    async def run(
        self,
        request: KeyInsightCheckInput,
        *,
        model_profile: str = "default",
        timeout: float = MODEL_REQUEST_TIMEOUT_SECONDS,
        trace_id: str = "local",
    ) -> KeyInsightAssessment:
        invocation = build_key_insight_check_invocation(request)
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
        return KeyInsightAssessment.model_validate(result)

    def run_sync(
        self, request: KeyInsightCheckInput, *, model_profile: str = "default"
    ) -> KeyInsightAssessment:
        return run_coro_sync(self.run(request, model_profile=model_profile))
