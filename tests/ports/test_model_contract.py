import pytest

from research_mentor.adapters.memory.model import ScriptedStructuredModel
from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.errors import ModelOutputInvalid
from research_mentor.ports.model import ModelRequest


REJECT_REVIEW = IdeaReviewOutput(
    idea_type="opinion",
    action="reject",
    normalized_idea="无法验证的主张",
    reason="缺少可检验研究问题",
    next_action="重新定义问题",
)


def request(trace_id: str) -> ModelRequest[IdeaReviewOutput]:
    return ModelRequest(
        agent_name="idea_review",
        model_profile="test",
        instructions="mentor",
        user_input="<idea>x</idea>",
        output_model=IdeaReviewOutput,
        timeout=10.0,
        trace_id=trace_id,
    )


@pytest.mark.asyncio
async def test_scripted_model_validates_requested_schema() -> None:
    model = ScriptedStructuredModel([REJECT_REVIEW.model_dump(mode="json")])

    result = await model.generate(request("trace-1"))

    assert isinstance(result, IdeaReviewOutput)
    assert result == REJECT_REVIEW


@pytest.mark.asyncio
async def test_scripted_model_rejects_wrong_schema() -> None:
    model = ScriptedStructuredModel([{"unexpected": True}])

    with pytest.raises(ModelOutputInvalid) as error:
        await model.generate(request("trace-2"))

    assert error.value.errors


def test_model_request_rejects_nonpositive_timeout() -> None:
    with pytest.raises(ValueError):
        ModelRequest(
            agent_name="idea_review",
            model_profile="test",
            instructions="mentor",
            user_input="<idea>x</idea>",
            output_model=IdeaReviewOutput,
            timeout=0,
            trace_id="trace-3",
        )
