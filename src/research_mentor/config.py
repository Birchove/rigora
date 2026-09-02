"""Configuration for the research mentor harness."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, HttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from research_mentor.domain.jobs import AgentName
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


VendorName = Literal["qwen", "deepseek", "chatgpt", "glm"]
SlotName = Literal["qwen", "deepseek", "chatgpt", "chatgpt_2", "glm"]
VendorApiStyle = Literal["chat_completions", "responses"]
VENDORS: tuple[VendorName, ...] = ("qwen", "deepseek", "chatgpt", "glm")
SLOTS: tuple[SlotName, ...] = ("qwen", "deepseek", "chatgpt", "chatgpt_2", "glm")
# high/mid/low 并行路径按此顺序取同时挂了 plan_loop 与 key_insight_check 的槽：一家提、下一家审
PARALLEL_SLOT_ORDER: tuple[SlotName, ...] = (
    "chatgpt",
    "chatgpt_2",
    "qwen",
    "glm",
    "deepseek",
)
ALL_AGENTS: tuple[AgentName, ...] = (
    "idea_review",
    "plan_loop",
    "key_insight_check",
    "working_qa",
    "complete",
)
SHARED_AGENTS: frozenset[AgentName] = frozenset({"plan_loop", "key_insight_check"})
AgentModeList = Annotated[list[AgentName], NoDecode]

# default API style, official base URL
VENDOR_PRESETS: dict[VendorName, tuple[VendorApiStyle, str]] = {
    "chatgpt": ("responses", "https://api.openai.com/v1"),
    "deepseek": ("chat_completions", "https://api.deepseek.com/v1"),
    "glm": ("chat_completions", "https://open.bigmodel.cn/api/paas/v4"),
    "qwen": (
        "chat_completions",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ),
}

VENDOR_DEFAULT_MODELS: dict[VendorName, str] = {
    "chatgpt": "gpt-4o-mini",
    "deepseek": "deepseek-chat",
    "glm": "glm-4-flash",
    "qwen": "qwen-plus",
}

_PLACEHOLDER_KEYS = frozenset({"xxxx", "XXXX"})
_ENV_FILE = None if os.environ.get("PYTEST_VERSION") else ".env"


class Settings(BaseSettings):
    """Application settings loaded from the environment and optional .env."""

    model_config = SettingsConfigDict(
        env_prefix="RESEARCH_MENTOR_",
        extra="forbid",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
    )

    qwen_api_key: SecretStr | None = None
    qwen_base_url: HttpUrl | None = None
    qwen_model: str | None = None
    qwen_api_style: VendorApiStyle | None = None
    qwen_agents: AgentModeList = Field(default_factory=list)
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: HttpUrl | None = None
    deepseek_model: str | None = None
    deepseek_api_style: VendorApiStyle | None = None
    deepseek_agents: AgentModeList = Field(default_factory=list)
    chatgpt_api_key: SecretStr | None = None
    chatgpt_base_url: HttpUrl | None = None
    chatgpt_model: str | None = None
    chatgpt_api_style: VendorApiStyle | None = None
    chatgpt_agents: AgentModeList = Field(default_factory=list)
    chatgpt_2_api_key: SecretStr | None = None
    chatgpt_2_base_url: HttpUrl | None = None
    chatgpt_2_model: str | None = None
    chatgpt_2_api_style: VendorApiStyle | None = None
    chatgpt_2_agents: AgentModeList = Field(default_factory=list)
    glm_api_key: SecretStr | None = None
    glm_base_url: HttpUrl | None = None
    glm_model: str | None = None
    glm_api_style: VendorApiStyle | None = None
    glm_agents: AgentModeList = Field(default_factory=list)
    model_provider: Literal["demo", "openai", "openai_compatible"] = "demo"
    model_name: str = "gpt-5-mini"
    model_base_url: HttpUrl | None = None
    model_api_key: SecretStr | None = None
    openalex_api_key: SecretStr | None = None
    openalex_mailto: str | None = None
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

    @field_validator(
        "qwen_agents",
        "deepseek_agents",
        "chatgpt_agents",
        "chatgpt_2_agents",
        "glm_agents",
        mode="before",
    )
    @classmethod
    def split_agent_modes(cls, value: object) -> object:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("[") and text.endswith("]"):
                text = text[1:-1]
            parts = [
                part.strip().strip("'\"")
                for part in text.replace(";", ",").split(",")
                if part.strip().strip("'\"")
            ]
        elif isinstance(value, (list, tuple)):
            parts = [str(item).strip() for item in value if str(item).strip()]
        else:
            return value
        if parts == ["all"]:
            return list(ALL_AGENTS)
        unique: list[str] = []
        for part in parts:
            if part not in unique:
                unique.append(part)
        return unique

    @model_validator(mode="after")
    def apply_placeholder_keys_and_vendor_slots(self) -> Self:
        for field_name in (
            "model_api_key",
            "qwen_api_key",
            "deepseek_api_key",
            "chatgpt_api_key",
            "chatgpt_2_api_key",
            "glm_api_key",
            "openalex_api_key",
        ):
            secret = getattr(self, field_name)
            if secret is None:
                continue
            raw = secret.get_secret_value().strip()
            if not raw or raw in _PLACEHOLDER_KEYS:
                setattr(self, field_name, None)
        claimed: dict[str, SlotName] = {}
        for slot in SLOTS:
            agents: list[AgentName] = getattr(self, f"{slot}_agents")
            if not agents:
                continue
            if self.slot_api_key(slot) is None:
                raise ValueError(f"{slot} agents assigned but API key is empty")
            if slot == "chatgpt_2" and not self.chatgpt_2_model:
                raise ValueError("chatgpt_2 agents assigned but model name is empty")
            if self.slot_api_style(slot) == "chat_completions" and not self.slot_base_url(slot):
                raise ValueError(f"{slot} chat_completions requires base_url")
            for agent in agents:
                if agent in SHARED_AGENTS:
                    continue
                previous = claimed.get(agent)
                if previous is not None:
                    raise ValueError(
                        f"agent {agent} is assigned to both {previous} and {slot}"
                    )
                claimed[agent] = slot
        return self

    def slot_api_key(self, slot: SlotName) -> SecretStr | None:
        secret = getattr(self, f"{slot}_api_key")
        if secret is None and slot == "chatgpt_2":
            return self.chatgpt_api_key
        return secret

    def slot_model(self, slot: SlotName) -> str:
        explicit = getattr(self, f"{slot}_model")
        if explicit:
            return explicit
        if slot == "chatgpt_2":
            return self.chatgpt_model or VENDOR_DEFAULT_MODELS["chatgpt"]
        return self.vendor_model(slot)

    def slot_base_url(self, slot: SlotName) -> str:
        explicit = getattr(self, f"{slot}_base_url")
        if explicit is not None:
            return str(explicit).rstrip("/")
        if slot == "chatgpt_2":
            return self.vendor_base_url("chatgpt")
        return self.vendor_base_url(slot)

    def slot_api_style(self, slot: SlotName) -> VendorApiStyle:
        explicit = getattr(self, f"{slot}_api_style")
        if explicit is not None:
            return explicit
        if slot == "chatgpt_2":
            return self.vendor_api_style("chatgpt")
        return self.vendor_api_style(slot)

    def parallel_slots(self) -> tuple[SlotName, ...]:
        return tuple(
            slot
            for slot in PARALLEL_SLOT_ORDER
            if SHARED_AGENTS.issubset(set(getattr(self, f"{slot}_agents")))
        )

    def plan_check_pairs(self) -> tuple[tuple[str, str], ...]:
        groups = self.parallel_slots()
        if not groups:
            return ()
        n = len(groups)
        pairs: list[tuple[str, str]] = []
        for index in range(3):
            plan_slot = groups[index % n]
            check_slot = groups[(index + 1) % n] if n > 1 else groups[0]
            pairs.append((self.slot_model(plan_slot), self.slot_model(check_slot)))
        return tuple(pairs)

    def vendor_model(self, vendor: VendorName) -> str:
        explicit = getattr(self, f"{vendor}_model")
        return explicit or VENDOR_DEFAULT_MODELS[vendor]

    def vendor_base_url(self, vendor: VendorName) -> str:
        explicit = getattr(self, f"{vendor}_base_url")
        if explicit is not None:
            return str(explicit).rstrip("/")
        return VENDOR_PRESETS[vendor][1]

    def vendor_api_style(self, vendor: VendorName) -> VendorApiStyle:
        explicit = getattr(self, f"{vendor}_api_style")
        return explicit or VENDOR_PRESETS[vendor][0]

    def agent_vendor_map(self) -> dict[AgentName, SlotName]:
        mapping: dict[AgentName, SlotName] = {}
        for slot in SLOTS:
            for agent in getattr(self, f"{slot}_agents"):
                mapping.setdefault(agent, slot)
        return mapping

    def agent_models(self) -> dict[str, str]:
        assigned = {"default": "default", **{agent: "default" for agent in ALL_AGENTS}}
        for slot in SLOTS:
            agents: list[AgentName] = getattr(self, f"{slot}_agents")
            if not agents:
                continue
            model = self.slot_model(slot)
            for agent in agents:
                assigned[agent] = model
        return assigned


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
    agent_models: dict[str, str] = field(default_factory=dict)
    plan_check_pairs: tuple[tuple[str, str], ...] = ()
    supported_domains: tuple[str, ...] = ("computer science",)
    supported_domain_aliases: tuple[str, ...] = ("cs", "计算机科学", "计算机")

    def model_for_agent(self, agent_name: str) -> str:
        return (
            self.agent_models.get(agent_name)
            or self.agent_models.get("default")
            or "default"
        )

    def plan_model_for_path(self, index: int) -> str:
        if self.plan_check_pairs:
            return self.plan_check_pairs[index][0]
        return self.model_for_agent("plan_loop")

    def check_model_for_path(self, index: int) -> str:
        if self.plan_check_pairs:
            return self.plan_check_pairs[index][1]
        return self.model_for_agent("key_insight_check")
