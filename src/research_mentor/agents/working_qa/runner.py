"""Runner for the Working QA Agent."""

from pydantic import BaseModel

from research_mentor.agents.working_qa.contracts import WorkingQAInput, WorkingQAOutput
from research_mentor.agents.working_qa.prompting import build_working_qa_invocation
from research_mentor.ports.model import StructuredModelPort


class WorkingQARunner:
    def __init__(self, model: StructuredModelPort) -> None:
        self._model = model

    def run(self, request: WorkingQAInput) -> WorkingQAOutput:
        invocation = build_working_qa_invocation(request)
        result = self._model.invoke(
            agent_name=invocation.agent_name,
            instructions=invocation.instructions,
            user_input=invocation.user_input,
            output_model=invocation.output_model,
        )
        if isinstance(result, BaseModel):
            result = result.model_dump(mode="python", warnings=False)
        return WorkingQAOutput.model_validate(result)
