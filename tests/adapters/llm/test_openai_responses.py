from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from research_mentor.adapters.model.openai_responses import (
    OpenAIResponsesModelAdapter,
)
from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.errors import ModelOutputInvalid
from research_mentor.ports.model import ModelRequest


REVIEW_OUTPUT = IdeaReviewOutput(
    idea_type="opinion",
    action="reject",
    normalized_idea="无法验证的主张",
    reason="缺少可检验研究问题",
    next_action="重新定义问题",
)

REVIEW_REQUEST = ModelRequest(
    agent_name="idea_review",
    model_profile="gpt-test",
    instructions="mentor instructions",
    user_input="<idea_review_data>{}</idea_review_data>",
    output_model=IdeaReviewOutput,
    timeout=12.0,
    trace_id="trace-responses",
)


@pytest.mark.asyncio
async def test_responses_adapter_returns_parsed_model() -> None:
    parse = AsyncMock(
        return_value=SimpleNamespace(
            output_parsed=REVIEW_OUTPUT,
            _request_id="req-responses",
            usage=SimpleNamespace(model_dump=lambda mode: {"input_tokens": 10}),
        )
    )
    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))

    result = await OpenAIResponsesModelAdapter(client).generate(REVIEW_REQUEST)

    assert result == REVIEW_OUTPUT
    kwargs = parse.await_args.kwargs
    assert kwargs == {
        "model": REVIEW_REQUEST.model_profile,
        "instructions": REVIEW_REQUEST.instructions,
        "input": REVIEW_REQUEST.user_input,
        "text_format": IdeaReviewOutput,
        "timeout": REVIEW_REQUEST.timeout,
    }


@pytest.mark.asyncio
async def test_responses_adapter_revalidates_parsed_model() -> None:
    invalid = IdeaReviewOutput.model_construct(
        idea_type="invalid",
        action="invalid",
        normalized_idea="n",
        reason="r",
        next_action="n",
    )
    parse = AsyncMock(
        return_value=SimpleNamespace(
            output_parsed=invalid,
            _request_id="req-invalid",
            usage=None,
        )
    )
    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))

    with pytest.raises(ModelOutputInvalid):
        await OpenAIResponsesModelAdapter(client).generate(REVIEW_REQUEST)
