"""Configuration for the research mentor harness."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from research_mentor.hyperparameters import (
    CHECK_DIMENSION_FLOORS,
    CHECK_PASS_SCORE,
    DOCUMENT_CHUNK_MAX_CHARS,
    DOCUMENT_CHUNK_OVERLAP_CHARS,
    MAX_CHECK_ROUNDS,
    RAG_RELEVANCE_THRESHOLD,
    RUN_LEASE_RENEWAL_SECONDS,
    RUN_LEASE_SECONDS,
    RUN_RETRY_LIMIT,
    RUN_TIMEOUT_SECONDS,
    SCORING_RULE_VERSION,
    SUPPORTED_DOMAIN_ALIASES,
    SUPPORTED_DOMAINS,
    UPLOAD_ALLOWED_EXTENSIONS,
    UPLOAD_ALLOWED_MEDIA_TYPES,
    UPLOAD_MAX_FILE_BYTES,
    UPLOAD_MAX_PROJECT_BYTES,
    WORKING_CONTEXT_CHARACTER_BUDGET,
)


class Settings(BaseSettings):
    """Application settings loaded from the environment."""

    model_config = SettingsConfigDict(env_prefix="RESEARCH_MENTOR_", extra="forbid")

    model_provider: Literal["demo", "openai", "openai_compatible"] = "demo"
    model_name: str = "gpt-5-mini"
    model_base_url: HttpUrl | None = None
    model_api_key: SecretStr | None = None
    database_url: str = "sqlite+aiosqlite:///./research_mentor.db"
    upload_root: Path = Path("./data/uploads")
    upload_allowed_media_types: tuple[str, ...] = UPLOAD_ALLOWED_MEDIA_TYPES
    upload_allowed_extensions: tuple[str, ...] = UPLOAD_ALLOWED_EXTENSIONS
    upload_max_file_bytes: int = Field(default=UPLOAD_MAX_FILE_BYTES, ge=1)
    upload_max_project_bytes: int = Field(default=UPLOAD_MAX_PROJECT_BYTES, ge=1)
    document_chunk_max_chars: int = Field(default=DOCUMENT_CHUNK_MAX_CHARS, ge=100)
    document_chunk_overlap_chars: int = Field(default=DOCUMENT_CHUNK_OVERLAP_CHARS, ge=0)
    public_base_url: HttpUrl = HttpUrl("http://localhost:8000")
    demo_mode: bool = True
    max_check_rounds: int = Field(default=MAX_CHECK_ROUNDS, ge=1)
    check_pass_score: float = Field(default=CHECK_PASS_SCORE, ge=0.0, le=10.0)
    rag_relevance_threshold: float = Field(default=RAG_RELEVANCE_THRESHOLD, ge=0.0, le=1.0)
    working_context_character_budget: int = Field(
        default=WORKING_CONTEXT_CHARACTER_BUDGET, ge=1000
    )
    run_lease_seconds: float = Field(default=RUN_LEASE_SECONDS, gt=0.0)
    run_lease_renewal_seconds: float = Field(default=RUN_LEASE_RENEWAL_SECONDS, gt=0.0)
    run_timeout_seconds: float = Field(default=RUN_TIMEOUT_SECONDS, gt=0.0)
    run_retry_limit: int = Field(default=RUN_RETRY_LIMIT, ge=1)
    supported_domains: tuple[str, ...] = SUPPORTED_DOMAINS
    supported_domain_aliases: tuple[str, ...] = SUPPORTED_DOMAIN_ALIASES


@dataclass(frozen=True, slots=True)
class HarnessConfig:
    """Immutable harness configuration and scoring defaults."""

    max_check_rounds: int = MAX_CHECK_ROUNDS
    pass_score: float = CHECK_PASS_SCORE
    rag_relevance_threshold: float = RAG_RELEVANCE_THRESHOLD
    scoring_rule_version: str = SCORING_RULE_VERSION
    dimension_floors: dict[str, float] = field(
        default_factory=lambda: dict(CHECK_DIMENSION_FLOORS)
    )
    supported_domains: tuple[str, ...] = ("computer science",)
    supported_domain_aliases: tuple[str, ...] = ("cs", "计算机科学", "计算机")
