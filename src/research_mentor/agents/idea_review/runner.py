"""Runner for the Idea Review Agent."""

from research_mentor.agents.idea_review.contracts import (
    IdeaReviewInput,
    IdeaReviewOutput,
)
from research_mentor.agents.idea_review.prompting import build_idea_review_invocation
from research_mentor.ports.model import StructuredModelPort
from pydantic import BaseModel


class IdeaReviewRunner:
    def __init__(self, model: StructuredModelPort) -> None:
        self._model = model

    def run(self, request: IdeaReviewInput) -> IdeaReviewOutput:
        invocation = build_idea_review_invocation(request)
        result = self._model.invoke(
            agent_name=invocation.agent_name,
            instructions=invocation.instructions,
            user_input=invocation.user_input,
            output_model=invocation.output_model,
        )
        if isinstance(result, BaseModel):
            result = result.model_dump(mode="python")
        return IdeaReviewOutput.model_validate(result)
