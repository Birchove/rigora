from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_mentor.config import HarnessConfig, Settings
from research_mentor.errors import (
    DuplicateSessionError,
    IllegalTransitionError,
    InvariantViolationError,
    PortExecutionError,
    ResearchMentorError,
    SessionNotFoundError,
)


@pytest.fixture(autouse=True)
def clear_settings_environment(monkeypatch):
    for name in (
        "RESEARCH_MENTOR_MODEL_PROVIDER",
        "RESEARCH_MENTOR_MODEL_NAME",
        "RESEARCH_MENTOR_MODEL_BASE_URL",
        "RESEARCH_MENTOR_MODEL_API_KEY",
        "RESEARCH_MENTOR_QWEN_API_KEY",
        "RESEARCH_MENTOR_QWEN_BASE_URL",
        "RESEARCH_MENTOR_QWEN_MODEL",
        "RESEARCH_MENTOR_QWEN_API_STYLE",
        "RESEARCH_MENTOR_QWEN_AGENTS",
        "RESEARCH_MENTOR_DEEPSEEK_API_KEY",
        "RESEARCH_MENTOR_DEEPSEEK_BASE_URL",
        "RESEARCH_MENTOR_DEEPSEEK_MODEL",
        "RESEARCH_MENTOR_DEEPSEEK_API_STYLE",
        "RESEARCH_MENTOR_DEEPSEEK_AGENTS",
        "RESEARCH_MENTOR_CHATGPT_API_KEY",
        "RESEARCH_MENTOR_CHATGPT_BASE_URL",
        "RESEARCH_MENTOR_CHATGPT_MODEL",
        "RESEARCH_MENTOR_CHATGPT_API_STYLE",
        "RESEARCH_MENTOR_CHATGPT_AGENTS",
        "RESEARCH_MENTOR_CHATGPT_2_API_KEY",
        "RESEARCH_MENTOR_CHATGPT_2_BASE_URL",
        "RESEARCH_MENTOR_CHATGPT_2_MODEL",
        "RESEARCH_MENTOR_CHATGPT_2_API_STYLE",
        "RESEARCH_MENTOR_CHATGPT_2_AGENTS",
        "RESEARCH_MENTOR_GLM_API_KEY",
        "RESEARCH_MENTOR_GLM_BASE_URL",
        "RESEARCH_MENTOR_GLM_MODEL",
        "RESEARCH_MENTOR_GLM_API_STYLE",
        "RESEARCH_MENTOR_GLM_AGENTS",
        "RESEARCH_MENTOR_DATABASE_URL",
        "RESEARCH_MENTOR_UPLOAD_ROOT",
        "RESEARCH_MENTOR_PUBLIC_BASE_URL",
        "RESEARCH_MENTOR_DEMO_MODE",
        "RESEARCH_MENTOR_MAX_CHECK_ROUNDS",
        "RESEARCH_MENTOR_CHECK_PASS_SCORE",
    ):
        monkeypatch.delenv(name, raising=False)


def test_harness_config_defaults():
    config = HarnessConfig()

    assert config.max_check_rounds == 5
    assert config.pass_score == 6.0
    assert config.rag_relevance_threshold == 0.3
    assert config.scoring_rule_version == "v1.1"
    assert config.dimension_floors["research_fit"] == 3.5
    assert config.dimension_floors["novelty"] == 3.0
    assert config.dimension_floors["research_value"] == 3.0
    assert config.dimension_floors["testability_feasibility"] == 3.0
    assert config.dimension_floors["evidence_support"] == 2.5


def test_harness_config_is_immutable():
    config = HarnessConfig()

    with pytest.raises(FrozenInstanceError):
        config.max_check_rounds = 6  # type: ignore[misc]


def test_settings_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("RESEARCH_MENTOR_MODEL_PROVIDER", "unknown")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_defaults_to_demo_and_sqlite():
    settings = Settings()

    assert settings.model_provider == "demo"
    assert settings.model_name == "gpt-5-mini"
    assert settings.model_base_url is None
    assert settings.model_api_key is None
    assert settings.qwen_agents == []
    assert settings.qwen_base_url is None
    assert settings.vendor_base_url("qwen") == (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    assert settings.vendor_api_style("chatgpt") == "responses"
    assert settings.vendor_api_style("qwen") == "chat_completions"
    assert settings.agent_models()["idea_review"] == "default"
    assert settings.database_url.startswith("sqlite+aiosqlite:///")
    assert settings.upload_root == Path("./data/uploads")
    assert str(settings.public_base_url) == "http://localhost:8000/"
    assert settings.demo_mode is True
    assert settings.max_check_rounds == 5
    assert settings.check_pass_score == 6.0


@pytest.mark.parametrize("provider", ("demo", "openai", "openai_compatible"))
def test_settings_accepts_supported_providers(monkeypatch, provider):
    monkeypatch.setenv("RESEARCH_MENTOR_MODEL_PROVIDER", provider)

    assert Settings().model_provider == provider


def test_settings_placeholder_api_key_is_ignored(monkeypatch):
    monkeypatch.setenv("RESEARCH_MENTOR_MODEL_API_KEY", "xxxx")
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_API_KEY", "xxxx")

    settings = Settings()

    assert settings.model_api_key is None
    assert settings.qwen_api_key is None


def test_settings_vendor_agents_are_multi_select(monkeypatch):
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_API_KEY", "qwen-test-key")
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_MODEL", "qwen-max")
    monkeypatch.setenv(
        "RESEARCH_MENTOR_QWEN_AGENTS", "idea_review,plan_loop,working_qa"
    )
    monkeypatch.setenv("RESEARCH_MENTOR_DEEPSEEK_API_KEY", "deepseek-test-key")
    monkeypatch.setenv("RESEARCH_MENTOR_DEEPSEEK_AGENTS", "key_insight_check,complete")

    settings = Settings()
    models = settings.agent_models()

    assert settings.agent_vendor_map() == {
        "idea_review": "qwen",
        "plan_loop": "qwen",
        "working_qa": "qwen",
        "key_insight_check": "deepseek",
        "complete": "deepseek",
    }
    assert models["idea_review"] == "qwen-max"
    assert models["plan_loop"] == "qwen-max"
    assert models["working_qa"] == "qwen-max"
    assert models["key_insight_check"] == "deepseek-chat"
    assert models["complete"] == "deepseek-chat"


def test_settings_all_alias_assigns_every_agent(monkeypatch):
    monkeypatch.setenv("RESEARCH_MENTOR_GLM_API_KEY", "glm-test-key")
    monkeypatch.setenv("RESEARCH_MENTOR_GLM_AGENTS", "all")

    settings = Settings()

    assert set(settings.glm_agents) == {
        "idea_review",
        "plan_loop",
        "key_insight_check",
        "working_qa",
        "complete",
    }
    assert settings.agent_models()["complete"] == "glm-4-flash"


def test_settings_rejects_unknown_agent_mode(monkeypatch):
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_API_KEY", "qwen-test-key")
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_AGENTS", "not_an_agent")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_duplicate_exclusive_agent_across_vendors(monkeypatch):
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_API_KEY", "qwen-test-key")
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_AGENTS", "idea_review")
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_API_KEY", "openai-test-key")
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_AGENTS", "idea_review,plan_loop")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_parses_bracket_agent_list(monkeypatch):
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_API_KEY", "qwen-test-key")
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_AGENTS", "[key_insight_check, plan_loop]")

    settings = Settings()

    assert settings.qwen_agents == ["key_insight_check", "plan_loop"]


def test_settings_allows_shared_plan_and_check_across_vendors(monkeypatch):
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_API_KEY", "openai-test-key")
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_MODEL", "gpt-plan")
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_AGENTS", "[key_insight_check, plan_loop]")
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_API_KEY", "qwen-test-key")
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_MODEL", "qwen-plan")
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_AGENTS", "[key_insight_check, plan_loop]")
    monkeypatch.setenv("RESEARCH_MENTOR_GLM_API_KEY", "glm-test-key")
    monkeypatch.setenv("RESEARCH_MENTOR_GLM_MODEL", "glm-plan")
    monkeypatch.setenv("RESEARCH_MENTOR_GLM_AGENTS", "[key_insight_check, plan_loop]")

    settings = Settings()

    assert settings.parallel_slots() == ("chatgpt", "qwen", "glm")
    assert settings.plan_check_pairs() == (
        ("gpt-plan", "qwen-plan"),
        ("qwen-plan", "glm-plan"),
        ("glm-plan", "gpt-plan"),
    )


def test_settings_chatgpt_2_inherits_key_for_second_model(monkeypatch):
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_API_KEY", "shared-openai-key")
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_BASE_URL", "https://relay.example/v1")
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_API_STYLE", "chat_completions")
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_AGENTS", "[key_insight_check, plan_loop]")
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_2_MODEL", "gpt-5.6-luna")
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_2_AGENTS", "working_qa")

    settings = Settings()

    assert settings.slot_api_key("chatgpt_2") is settings.chatgpt_api_key
    assert settings.slot_base_url("chatgpt_2") == "https://relay.example/v1"
    assert settings.slot_api_style("chatgpt_2") == "chat_completions"
    assert settings.slot_model("chatgpt_2") == "gpt-5.6-luna"


def test_settings_chatgpt_2_joins_parallel_plan_paths(monkeypatch):
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_API_KEY", "shared-openai-key")
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_AGENTS", "working_qa")
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_2_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_2_AGENTS", "[key_insight_check, plan_loop]")
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_API_KEY", "qwen-test-key")
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_MODEL", "qwen-plan")
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_AGENTS", "[key_insight_check, plan_loop]")
    monkeypatch.setenv("RESEARCH_MENTOR_GLM_API_KEY", "glm-test-key")
    monkeypatch.setenv("RESEARCH_MENTOR_GLM_MODEL", "glm-plan")
    monkeypatch.setenv("RESEARCH_MENTOR_GLM_AGENTS", "[key_insight_check, plan_loop]")

    settings = Settings()

    assert settings.parallel_slots() == ("chatgpt_2", "qwen", "glm")
    assert settings.plan_check_pairs() == (
        ("gpt-5.6-sol", "qwen-plan"),
        ("qwen-plan", "glm-plan"),
        ("glm-plan", "gpt-5.6-sol"),
    )


def test_settings_requires_key_when_agents_assigned(monkeypatch):
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_AGENTS", "idea_review")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_vendor_base_url_and_style_override(monkeypatch):
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_API_KEY", "qwen-test-key")
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_BASE_URL", "https://relay.example/v1")
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_API_STYLE", "chat_completions")
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_AGENTS", "idea_review")
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_API_KEY", "openai-test-key")
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_BASE_URL", "https://relay.example/openai")
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_API_STYLE", "chat_completions")
    monkeypatch.setenv("RESEARCH_MENTOR_CHATGPT_AGENTS", "plan_loop")

    settings = Settings()

    assert settings.vendor_base_url("qwen") == "https://relay.example/v1"
    assert settings.vendor_api_style("qwen") == "chat_completions"
    assert settings.vendor_base_url("chatgpt") == "https://relay.example/openai"
    assert settings.vendor_api_style("chatgpt") == "chat_completions"
    assert settings.vendor_base_url("glm") == "https://open.bigmodel.cn/api/paas/v4"


def test_settings_rejects_unknown_api_style(monkeypatch):
    monkeypatch.setenv("RESEARCH_MENTOR_QWEN_API_STYLE", "grpc")

    with pytest.raises(ValidationError):
        Settings()


def test_harness_config_model_for_agent():
    config = HarnessConfig(agent_models={"default": "qwen-plus", "plan_loop": "qwen-max"})

    assert config.model_for_agent("plan_loop") == "qwen-max"
    assert config.model_for_agent("idea_review") == "qwen-plus"
    assert HarnessConfig().model_for_agent("idea_review") == "default"


def test_domain_errors_derive_from_research_mentor_error():
    error_types = (
        DuplicateSessionError,
        IllegalTransitionError,
        InvariantViolationError,
        PortExecutionError,
        SessionNotFoundError,
    )

    assert all(issubclass(error_type, ResearchMentorError) for error_type in error_types)
