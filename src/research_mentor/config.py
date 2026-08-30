"""Configuration for the research mentor harness."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HarnessConfig:
    """Immutable harness configuration and scoring defaults."""

    max_check_rounds: int = 5
    pass_score: float = 6.0
    rag_relevance_threshold: float = 0.3
    scoring_rule_version: str = "v1"
