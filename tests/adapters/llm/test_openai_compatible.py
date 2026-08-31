from unittest.mock import AsyncMock

import httpx
import pytest

from research_mentor.adapters.model.errors import ModelTemporarilyUnavailable
from research_mentor.adapters.model.openai_compatible import (
    OpenAICompatibleModelAdapter,
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
    model_profile="compatible-test",
    instructions="mentor instructions",
    user_input="<idea_review_data>{}</idea_review_data>",
    output_model=IdeaReviewOutput,
    timeout=9.0,
    trace_id="trace-compatible",
)


def response(status_code: int, payload: dict) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("POST", "https://provider.test/v1/chat/completions"),
    )


@pytest.mark.asyncio
async def test_compatible_adapter_sends_schema_and_validates_content() -> None:
    client = AsyncMock()
    client.post.return_value = response(
        200,
        {
            "id": "req-compatible",
            "usage": {"prompt_tokens": 8, "completion_tokens": 4},
            "choices": [
                {"message": {"content": REVIEW_OUTPUT.model_dump_json()}}
            ],
        },
    )

    result = await OpenAICompatibleModelAdapter(
        client, base_url="https://provider.test/v1/"
    ).generate(REVIEW_REQUEST)

    assert result == REVIEW_OUTPUT
    client.post.assert_awaited_once()
    args, kwargs = client.post.await_args
    assert args == ("https://provider.test/v1/chat/completions",)
    assert kwargs["timeout"] == REVIEW_REQUEST.timeout
    assert kwargs["json"]["model"] == REVIEW_REQUEST.model_profile
    assert kwargs["json"]["messages"] == [
        {"role": "system", "content": REVIEW_REQUEST.instructions},
        {"role": "user", "content": REVIEW_REQUEST.user_input},
    ]
    assert (
        kwargs["json"]["response_format"]["json_schema"]["schema"]
        == IdeaReviewOutput.model_json_schema()
    )


@pytest.mark.asyncio
async def test_compatible_adapter_maps_invalid_json() -> None:
    client = AsyncMock()
    client.post.return_value = response(
        200,
        {"choices": [{"message": {"content": "not-json"}}]},
    )

    with pytest.raises(ModelOutputInvalid):
        await OpenAICompatibleModelAdapter(
            client, base_url="https://provider.test/v1"
        ).generate(REVIEW_REQUEST)


@pytest.mark.asyncio
async def test_compatible_adapter_maps_transient_http_status() -> None:
    client = AsyncMock()
    client.post.return_value = response(429, {"error": {"message": "limited"}})

    with pytest.raises(ModelTemporarilyUnavailable):
        await OpenAICompatibleModelAdapter(
            client, base_url="https://provider.test/v1"
        ).generate(REVIEW_REQUEST)
