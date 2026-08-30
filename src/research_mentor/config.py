"""Configuration for the research mentor harness."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from the environment."""

    model_config = SettingsConfigDict(env_prefix="RESEARCH_MENTOR_", extra="forbid")

    model_provider: Literal["demo", "openai", "openai_compatible"] = "demo"
    model_name: str = "gpt-5-mini"
    model_base_url: HttpUrl | None = None
    model_api_key: SecretStr | None = None
    database_url: str = "sqlite+aiosqlite:///./research_mentor.db"
    upload_root: Path = Path("./data/uploads")
    public_base_url: HttpUrl = HttpUrl("http://localhost:8000")
    demo_mode: bool = True


@dataclass(frozen=True, slots=True)
class HarnessConfig:
    """Immutable harness configuration and scoring defaults."""

    max_check_rounds: int = 5
    pass_score: float = 6.0
    rag_relevance_threshold: float = 0.3
    scoring_rule_version: str = "v1"
