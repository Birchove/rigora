"""Local runs must never silently fall back to demo fixtures."""

import pytest
from pydantic import SecretStr

from research_mentor.adapters.demo.model import DemoModelAdapter
from research_mentor.adapters.model.routing import RoutingModelAdapter
from research_mentor.bootstrap import _build_model, _use_openalex
from research_mentor.config import ALL_AGENTS, Settings
from research_mentor.errors import ConfigurationIncomplete


def _full_coverage_settings() -> Settings:
    return Settings(
        qwen_api_key=SecretStr("sk-test"),
        qwen_base_url="https://api.example/v1",
        qwen_api_style="chat_completions",
        qwen_agents=list(ALL_AGENTS),
    )


def test_unconfigured_settings_refuse_to_build_a_model():
    with pytest.raises(ConfigurationIncomplete, match="rigora-setup"):
        _build_model(Settings())


def test_partial_agent_coverage_is_refused():
    settings = Settings(
        qwen_api_key=SecretStr("sk-test"),
        qwen_base_url="https://api.example/v1",
        qwen_agents=["idea_review"],
    )

    with pytest.raises(ConfigurationIncomplete) as error:
        _build_model(settings)

    message = str(error.value)
    for agent in ("plan_loop", "key_insight_check", "working_qa", "complete"):
        assert agent in message


@pytest.mark.asyncio
async def test_full_coverage_routes_without_a_demo_fallback():
    model, closer = _build_model(_full_coverage_settings())

    assert isinstance(model, RoutingModelAdapter)
    assert not isinstance(model._fallback, DemoModelAdapter)
    for agent in ALL_AGENTS:
        assert not isinstance(model._routes[agent], DemoModelAdapter)
    assert closer is not None
    await closer()


def test_demo_remains_available_only_as_an_explicit_opt_in():
    model, closer = _build_model(Settings(model_provider="demo"))

    assert isinstance(model, DemoModelAdapter)
    assert closer is None


def test_openalex_is_skipped_for_unset_and_demo_only():
    assert _use_openalex(Settings()) is False
    assert _use_openalex(Settings(model_provider="demo")) is False
    assert _use_openalex(_full_coverage_settings()) is True
