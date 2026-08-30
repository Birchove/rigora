from dataclasses import FrozenInstanceError

import pytest

from research_mentor.config import HarnessConfig
from research_mentor.errors import (
    DuplicateSessionError,
    IllegalTransitionError,
    InvariantViolationError,
    PortExecutionError,
    ResearchMentorError,
    SessionNotFoundError,
)


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


def test_domain_errors_derive_from_research_mentor_error():
    error_types = (
        DuplicateSessionError,
        IllegalTransitionError,
        InvariantViolationError,
        PortExecutionError,
        SessionNotFoundError,
    )

    assert all(issubclass(error_type, ResearchMentorError) for error_type in error_types)
