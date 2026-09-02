"""Runner for the Idea Review Agent."""

from pydantic import BaseModel

from research_mentor.agents.idea_review.contracts import (
    IdeaReviewInput,
    IdeaReviewOutput,
)
from research_mentor.agents.idea_review.prompting import build_idea_review_invocation
from research_mentor.hyperparameters import MODEL_REQUEST_TIMEOUT_SECONDS
from research_mentor.ports.model import ModelRequest, StructuredModelPort
from research_mentor.runtime_async import run_coro_sync


class IdeaReviewRunner:
    def __init__(self, model: StructuredModelPort) -> None:
        self._model = model

    async def run(
        self,
        request: IdeaReviewInput,
        *,
        model_profile: str = "default",
        timeout: float = MODEL_REQUEST_TIMEOUT_SECONDS,
        trace_id: str = "local",
    ) -> IdeaReviewOutput:
        invocation = build_idea_review_invocation(request)
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
        return IdeaReviewOutput.model_validate(result)

    def run_sync(
        self, request: IdeaReviewInput, *, model_profile: str = "default"
    ) -> IdeaReviewOutput:
        return run_coro_sync(self.run(request, model_profile=model_profile))
