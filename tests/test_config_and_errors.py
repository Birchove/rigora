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
    assert config.scoring_rule_version == "v1"
    assert "min_dimension_score" not in config.__dataclass_fields__


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


def test_domain_errors_derive_from_research_mentor_error():
    error_types = (
        DuplicateSessionError,
        IllegalTransitionError,
        InvariantViolationError,
        PortExecutionError,
        SessionNotFoundError,
    )

    assert all(issubclass(error_type, ResearchMentorError) for error_type in error_types)
