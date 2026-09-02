import pytest
from pydantic import SecretStr

from research_mentor.adapters.model.openai_compatible import (
    OpenAICompatibleModelAdapter,
)
from research_mentor.adapters.model.openai_responses import (
    OpenAIResponsesModelAdapter,
)
from research_mentor.bootstrap import _build_vendor_adapter
from research_mentor.config import Settings


@pytest.mark.asyncio
async def test_build_vendor_adapter_uses_relay_chat_completions() -> None:
    settings = Settings(
        qwen_api_key=SecretStr("test-key"),
        qwen_base_url="https://relay.example/v1",
        qwen_api_style="chat_completions",
        qwen_agents=["idea_review"],
    )

    adapter, closer = _build_vendor_adapter(settings, "qwen")

    assert isinstance(adapter, OpenAICompatibleModelAdapter)
    assert adapter._endpoint == "https://relay.example/v1/chat/completions"
    assert closer is not None
    await closer()


@pytest.mark.asyncio
async def test_build_vendor_adapter_uses_responses_with_base_url() -> None:
    settings = Settings(
        chatgpt_api_key=SecretStr("test-key"),
        chatgpt_base_url="https://api.openai.com/v1",
        chatgpt_api_style="responses",
        chatgpt_agents=["idea_review"],
    )

    adapter, closer = _build_vendor_adapter(settings, "chatgpt")

    assert isinstance(adapter, OpenAIResponsesModelAdapter)
    assert closer is not None
    await closer()
