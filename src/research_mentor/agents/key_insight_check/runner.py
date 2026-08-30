"""Runner for the Key Insight Check Agent."""

from pydantic import BaseModel

from research_mentor.agents.key_insight_check.contracts import (
    KeyInsightAssessment,
    KeyInsightCheckInput,
)
from research_mentor.agents.key_insight_check.prompting import (
    build_key_insight_check_invocation,
)
from research_mentor.ports.model import StructuredModelPort


class KeyInsightCheckRunner:
    def __init__(self, model: StructuredModelPort) -> None:
        self._model = model

    def run(self, request: KeyInsightCheckInput) -> KeyInsightAssessment:
        invocation = build_key_insight_check_invocation(request)
        result = self._model.invoke(
            agent_name=invocation.agent_name,
            instructions=invocation.instructions,
            user_input=invocation.user_input,
            output_model=invocation.output_model,
        )
        if isinstance(result, BaseModel):
            result = result.model_dump(mode="python", warnings=False)
        return KeyInsightAssessment.model_validate(result)
