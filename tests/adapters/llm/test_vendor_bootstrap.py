import pytest
from pydantic import SecretStr

from research_mentor.adapters.model.openai_compatible import (
    OpenAICompatibleModelAdapter,
)
from research_mentor.adapters.model.openai_responses import (
    OpenAIResponsesModelAdapter,
)
from research_mentor.bootstrap import _build_vendor_adapter, _use_openalex
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
    assert adapter._response_format_mode == "json_object"
    assert adapter._client.trust_env is True
    assert closer is not None
    await closer()


@pytest.mark.asyncio
async def test_qwen_domestic_gateway_bypasses_system_proxy() -> None:
    settings = Settings(
        qwen_api_key=SecretStr("test-key"),
        qwen_base_url="https://maas-openapi.wanjiedata.com/api/v1",
        qwen_api_style="chat_completions",
        qwen_agents=["key_insight_check"],
    )

    adapter, closer = _build_vendor_adapter(settings, "qwen")

    assert isinstance(adapter, OpenAICompatibleModelAdapter)
    assert adapter._client.trust_env is False
    assert closer is not None
    await closer()


@pytest.mark.asyncio
async def test_build_vendor_adapter_uses_json_object_for_deepseek() -> None:
    settings = Settings(
        deepseek_api_key=SecretStr("test-key"),
        deepseek_base_url="https://api.deepseek.com",
        deepseek_api_style="chat_completions",
        deepseek_agents=["idea_review"],
    )

    adapter, closer = _build_vendor_adapter(settings, "deepseek")

    assert isinstance(adapter, OpenAICompatibleModelAdapter)
    assert adapter._response_format_mode == "json_object"
    assert closer is not None
    await closer()


@pytest.mark.asyncio
async def test_build_vendor_adapter_uses_json_object_for_chatgpt_relay() -> None:
    settings = Settings(
        chatgpt_api_key=SecretStr("test-key"),
        chatgpt_base_url="https://relay.example/v1",
        chatgpt_api_style="chat_completions",
        chatgpt_agents=["working_qa"],
        chatgpt_2_model="gpt-relay-2",
        chatgpt_2_agents=["plan_loop", "key_insight_check"],
    )

    adapter, closer = _build_vendor_adapter(settings, "chatgpt_2")

    assert isinstance(adapter, OpenAICompatibleModelAdapter)
    assert adapter._endpoint == "https://relay.example/v1/chat/completions"
    assert adapter._response_format_mode == "json_object"
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


def test_use_openalex_when_vendor_agents_are_configured() -> None:
    demo_only = Settings(model_provider="demo", demo_mode=True)
    with_vendor = Settings(
        model_provider="demo",
        demo_mode=True,
        deepseek_api_key=SecretStr("test-key"),
        deepseek_agents=["idea_review"],
    )
    assert _use_openalex(demo_only) is False
    assert _use_openalex(with_vendor) is True
