"""Configuration for the research mentor harness."""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, HttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from research_mentor.domain.jobs import AgentName
from research_mentor.adapters.embeddings.huggingface_hub_env import resolve_hf_endpoint
from research_mentor.hyperparameters import (
    CHECK_DIMENSION_FLOORS,
    CHECK_PASS_SCORE,
    DOCUMENT_CHUNK_MAX_CHARS,
    DOCUMENT_CHUNK_OVERLAP_CHARS,
    MAX_CHECK_ROUNDS,
    PLAN_CANDIDATE_MAX,
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
    DEFAULT_RERANKER_CACHE_DIR,
    DEFAULT_RERANKER_MODEL,
)


VendorName = Literal[
    "qwen",
    "deepseek",
    "chatgpt",
    "claude",
    "gemini",
    "glm",
    "kimi",
    "minimax",
    "doubao",
    "hunyuan",
    "stepfun",
    "longcat",
    "mimo",
    "grok",
    "bailing",
    "qianfan",
]
RerankerBackend = Literal["auto", "flagembedding", "lexical", "unavailable"]
SlotName = Literal[
    "qwen",
    "deepseek",
    "chatgpt",
    "chatgpt_2",
    "claude",
    "gemini",
    "glm",
    "kimi",
    "minimax",
    "doubao",
    "hunyuan",
    "stepfun",
    "longcat",
    "mimo",
    "grok",
    "bailing",
    "qianfan",
]
VendorApiStyle = Literal["chat_completions", "responses"]
VENDORS: tuple[VendorName, ...] = (
    "qwen",
    "deepseek",
    "chatgpt",
    "claude",
    "gemini",
    "glm",
    "kimi",
    "minimax",
    "doubao",
    "hunyuan",
    "stepfun",
    "longcat",
    "mimo",
    "grok",
    "bailing",
    "qianfan",
)
SLOTS: tuple[SlotName, ...] = (
    "qwen",
    "deepseek",
    "chatgpt",
    "chatgpt_2",
    "claude",
    "gemini",
    "glm",
    "kimi",
    "minimax",
    "doubao",
    "hunyuan",
    "stepfun",
    "longcat",
    "mimo",
    "grok",
    "bailing",
    "qianfan",
)
# high/mid/low 并行路径按此顺序取同时挂了 plan_loop 与 key_insight_check 的槽：一家提、下一家审
PARALLEL_SLOT_ORDER: tuple[SlotName, ...] = (
    "chatgpt",
    "chatgpt_2",
    "claude",
    "gemini",
    "qwen",
    "glm",
    "deepseek",
    "kimi",
    "minimax",
    "doubao",
    "hunyuan",
    "stepfun",
    "longcat",
    "mimo",
    "grok",
    "bailing",
    "qianfan",
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

# 厂商名单与默认模型对齐 cc-switch 的 Codex 预设；Claude / Gemini 不在
# 那份名单里（cc-switch 把它们放在 Claude / Gemini 应用下），这里补官方
# OpenAI 兼容端点。面板里模型名自填，这里只预填便宜快的默认型号。
# 聚合中转和 OAuth 官方登录不收录。
VENDOR_PRESETS: dict[VendorName, tuple[VendorApiStyle, str]] = {
    "chatgpt": ("responses", "https://api.openai.com/v1"),
    "claude": ("chat_completions", "https://api.anthropic.com/v1"),
    "gemini": (
        "chat_completions",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    ),
    "deepseek": ("chat_completions", "https://api.deepseek.com"),
    "glm": ("chat_completions", "https://open.bigmodel.cn/api/paas/v4"),
    "qwen": (
        "chat_completions",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ),
    "kimi": ("chat_completions", "https://api.moonshot.cn/v1"),
    "minimax": ("chat_completions", "https://api.minimaxi.com/v1"),
    "doubao": ("chat_completions", "https://ark.cn-beijing.volces.com/api/v3"),
    "hunyuan": ("chat_completions", "https://tokenhub.tencentmaas.com/v1"),
    "stepfun": ("chat_completions", "https://api.stepfun.com/step_plan/v1"),
    "longcat": ("chat_completions", "https://api.longcat.chat/openai/v1"),
    "mimo": ("chat_completions", "https://api.xiaomimimo.com/v1"),
    "grok": ("chat_completions", "https://api.x.ai/v1"),
    "bailing": ("chat_completions", "https://api.tbox.cn/api/llm/v1"),
    "qianfan": (
        "chat_completions",
        "https://qianfan.baidubce.com/v2/tokenplan/personal",
    ),
}

VENDOR_DEFAULT_MODELS: dict[VendorName, str] = {
    "chatgpt": "gpt-5.6-luna",
    "claude": "claude-haiku-4.5",
    "gemini": "gemini-3.8-flash",
    "deepseek": "deepseek-v4-flash",
    "glm": "glm-5.3",
    "qwen": "qwen3-coder-plus",
    "kimi": "kimi-k2.7-code",
    "minimax": "MiniMax-M3",
    "doubao": "doubao-seed-2-1-pro-260628",
    "hunyuan": "hy3",
    "stepfun": "step-3.7-flash",
    "longcat": "LongCat-2.0",
    "mimo": "mimo-v2.5-pro",
    "grok": "grok-4.5",
    "bailing": "Ling-2.6-1T",
    "qianfan": "deepseek-v4-flash",
}

VENDOR_LABELS: dict[VendorName, str] = {
    "chatgpt": "ChatGPT",
    "claude": "Claude",
    "gemini": "Gemini",
    "deepseek": "DeepSeek",
    "glm": "GLM",
    "qwen": "千问 Qwen",
    "kimi": "Kimi",
    "minimax": "MiniMax",
    "doubao": "豆包 Doubao",
    "hunyuan": "混元 Hunyuan",
    "stepfun": "阶跃星辰",
    "longcat": "LongCat",
    "mimo": "小米 MiMo",
    "grok": "xAI Grok",
    "bailing": "百灵 BaiLing",
    "qianfan": "千帆 Qianfan",
}

# 预填 cc-switch 该预设的默认型号；面板里可改成任意可用名称。
VENDOR_MODEL_OPTIONS: dict[VendorName, tuple[str, ...]] = {
    vendor: (model,) for vendor, model in VENDOR_DEFAULT_MODELS.items()
}

# chatgpt_2 是「同一把 ChatGPT key 的第二个模型」，凭据默认继承主槽。
SLOT_VENDOR: dict[SlotName, VendorName] = {
    "qwen": "qwen",
    "deepseek": "deepseek",
    "chatgpt": "chatgpt",
    "chatgpt_2": "chatgpt",
    "claude": "claude",
    "gemini": "gemini",
    "glm": "glm",
    "kimi": "kimi",
    "minimax": "minimax",
    "doubao": "doubao",
    "hunyuan": "hunyuan",
    "stepfun": "stepfun",
    "longcat": "longcat",
    "mimo": "mimo",
    "grok": "grok",
    "bailing": "bailing",
    "qianfan": "qianfan",
}

# 引导面板一家一个槽。chatgpt_2 只留给手工编辑 .env。
PANEL_SLOTS: tuple[SlotName, ...] = VENDORS  # VendorName 是 SlotName 的子集

# 国内网关走系统 HTTP 代理时经常读超时或触发 Windows 10013；这些 host 直连。
DIRECT_CONNECT_MARKERS: tuple[str, ...] = (
    "wanjiedata.com",
    "dashscope.aliyuncs.com",
    "bigmodel.cn",
    "api.deepseek.com",
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.moonshot.cn",
    "api.minimaxi.com",
    "volces.com",
    "tencentmaas.com",
    "api.stepfun.com",
    "api.longcat.chat",
    "xiaomimimo.com",
    "api.x.ai",
    "api.tbox.cn",
    "qianfan.baidubce.com",
)


def direct_connect(base_url: str) -> bool:
    return any(marker in base_url for marker in DIRECT_CONNECT_MARKERS)


def vendor_http_headers(base_url: str, api_key: str) -> dict[str, str]:
    """Auth headers for a vendor slot. Anthropic 官方同时认 Bearer 和 x-api-key。"""
    headers = {"Authorization": f"Bearer {api_key}"}
    if "anthropic.com" in base_url:
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    return headers


PLAN_CHECK_PAIR_MAX = PLAN_CANDIDATE_MAX


def parse_plan_check_spec(raw: str) -> tuple[tuple[str, str], ...]:
    """Parse `plan>check,plan>check` into ordered slot pairs."""
    entries = [
        part.strip() for part in raw.replace(";", ",").split(",") if part.strip()
    ]
    pairs: list[tuple[str, str]] = []
    for entry in entries:
        plan, separator, check = entry.partition(">")
        if not separator or not plan.strip() or not check.strip():
            raise ValueError(
                f"配对 {entry!r} 格式不对，应为 提案槽>评审槽，例如 qwen>glm"
            )
        pairs.append((plan.strip(), check.strip()))
    return tuple(pairs)


def format_plan_check_spec(pairs: Sequence[tuple[str, str]]) -> str:
    return ",".join(f"{plan}>{check}" for plan, check in pairs)


_PLACEHOLDER_KEYS = frozenset({"xxxx", "XXXX"})
_ENV_FILE = None if os.environ.get("PYTEST_VERSION") else ".env"
logger = logging.getLogger("research_mentor.config")


class Settings(BaseSettings):
    """Application settings loaded from the environment and optional .env."""

    model_config = SettingsConfigDict(
        env_prefix="RESEARCH_MENTOR_",
        extra="forbid",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        # plan_check_pairs_spec 用了显式 validation_alias，构造时仍要能按字段名传。
        populate_by_name=True,
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
    claude_api_key: SecretStr | None = None
    claude_base_url: HttpUrl | None = None
    claude_model: str | None = None
    claude_api_style: VendorApiStyle | None = None
    claude_agents: AgentModeList = Field(default_factory=list)
    gemini_api_key: SecretStr | None = None
    gemini_base_url: HttpUrl | None = None
    gemini_model: str | None = None
    gemini_api_style: VendorApiStyle | None = None
    gemini_agents: AgentModeList = Field(default_factory=list)
    glm_api_key: SecretStr | None = None
    glm_base_url: HttpUrl | None = None
    glm_model: str | None = None
    glm_api_style: VendorApiStyle | None = None
    glm_agents: AgentModeList = Field(default_factory=list)
    kimi_api_key: SecretStr | None = None
    kimi_base_url: HttpUrl | None = None
    kimi_model: str | None = None
    kimi_api_style: VendorApiStyle | None = None
    kimi_agents: AgentModeList = Field(default_factory=list)
    minimax_api_key: SecretStr | None = None
    minimax_base_url: HttpUrl | None = None
    minimax_model: str | None = None
    minimax_api_style: VendorApiStyle | None = None
    minimax_agents: AgentModeList = Field(default_factory=list)
    doubao_api_key: SecretStr | None = None
    doubao_base_url: HttpUrl | None = None
    doubao_model: str | None = None
    doubao_api_style: VendorApiStyle | None = None
    doubao_agents: AgentModeList = Field(default_factory=list)
    hunyuan_api_key: SecretStr | None = None
    hunyuan_base_url: HttpUrl | None = None
    hunyuan_model: str | None = None
    hunyuan_api_style: VendorApiStyle | None = None
    hunyuan_agents: AgentModeList = Field(default_factory=list)
    stepfun_api_key: SecretStr | None = None
    stepfun_base_url: HttpUrl | None = None
    stepfun_model: str | None = None
    stepfun_api_style: VendorApiStyle | None = None
    stepfun_agents: AgentModeList = Field(default_factory=list)
    longcat_api_key: SecretStr | None = None
    longcat_base_url: HttpUrl | None = None
    longcat_model: str | None = None
    longcat_api_style: VendorApiStyle | None = None
    longcat_agents: AgentModeList = Field(default_factory=list)
    mimo_api_key: SecretStr | None = None
    mimo_base_url: HttpUrl | None = None
    mimo_model: str | None = None
    mimo_api_style: VendorApiStyle | None = None
    mimo_agents: AgentModeList = Field(default_factory=list)
    grok_api_key: SecretStr | None = None
    grok_base_url: HttpUrl | None = None
    grok_model: str | None = None
    grok_api_style: VendorApiStyle | None = None
    grok_agents: AgentModeList = Field(default_factory=list)
    bailing_api_key: SecretStr | None = None
    bailing_base_url: HttpUrl | None = None
    bailing_model: str | None = None
    bailing_api_style: VendorApiStyle | None = None
    bailing_agents: AgentModeList = Field(default_factory=list)
    qianfan_api_key: SecretStr | None = None
    qianfan_base_url: HttpUrl | None = None
    qianfan_model: str | None = None
    qianfan_api_style: VendorApiStyle | None = None
    qianfan_agents: AgentModeList = Field(default_factory=list)
    # 有序的「提案槽>评审槽」列表，最多 3 对，例如 qwen>glm,chatgpt>deepseek。
    # 留空则退回按 PARALLEL_SLOT_ORDER 轮转的旧行为。
    # 字段名带 _spec 是因为 plan_check_pairs 已经是方法名，所以显式给出环境变量名。
    plan_check_pairs_spec: str = Field(
        default="", validation_alias="RESEARCH_MENTOR_PLAN_CHECK_PAIRS"
    )
    # 恰好 2 对时，high 模式的第三条路取哪个交错组合：
    # ad = 第一家提·第二家审，bc = 第二家提·第一家审。
    plan_check_high_cross: Literal["off", "ad", "bc"] = "off"
    # unset: 没有旧式单模型配置。此时必须由 vendor slot 提供全部 Agent，
    # 否则 bootstrap 直接报错，不静默退化成 demo fixture。
    model_provider: Literal["unset", "demo", "openai", "openai_compatible"] = "unset"
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
    demo_mode: bool = False
    max_check_rounds: int = Field(default=MAX_CHECK_ROUNDS, ge=1)
    check_pass_score: float = Field(default=CHECK_PASS_SCORE, ge=0.0, le=10.0)
    rag_relevance_threshold: float = Field(default=RAG_RELEVANCE_THRESHOLD, ge=0.0, le=1.0)
    working_context_character_budget: int = Field(
        default=WORKING_CONTEXT_CHARACTER_BUDGET, ge=1000
    )
    reranker_backend: RerankerBackend = "auto"
    reranker_model: str = DEFAULT_RERANKER_MODEL
    reranker_cache_dir: Path = Path(DEFAULT_RERANKER_CACHE_DIR)
    hf_endpoint: str | None = None
    hf_token: SecretStr | None = None
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
        "claude_agents",
        "gemini_agents",
        "glm_agents",
        "kimi_agents",
        "minimax_agents",
        "doubao_agents",
        "hunyuan_agents",
        "stepfun_agents",
        "longcat_agents",
        "mimo_agents",
        "grok_agents",
        "bailing_agents",
        "qianfan_agents",
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

    @field_validator("hf_endpoint", mode="before")
    @classmethod
    def normalize_hf_endpoint(cls, value: object) -> object:
        if value is None or value == "":
            return None
        return resolve_hf_endpoint(str(value))

    @model_validator(mode="after")
    def apply_placeholder_keys_and_vendor_slots(self) -> Self:
        for field_name in (
            "model_api_key",
            "qwen_api_key",
            "deepseek_api_key",
            "chatgpt_api_key",
            "chatgpt_2_api_key",
            "claude_api_key",
            "gemini_api_key",
            "glm_api_key",
            "kimi_api_key",
            "minimax_api_key",
            "doubao_api_key",
            "hunyuan_api_key",
            "stepfun_api_key",
            "longcat_api_key",
            "mimo_api_key",
            "grok_api_key",
            "bailing_api_key",
            "qianfan_api_key",
            "openalex_api_key",
            "hf_token",
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
        self._validate_plan_check_spec()
        return self

    def _validate_plan_check_spec(self) -> None:
        raw = self.plan_check_pairs_spec.strip()
        if not raw:
            return
        pairs = parse_plan_check_spec(raw)
        if len(pairs) > PLAN_CHECK_PAIR_MAX:
            raise ValueError(
                f"plan_check_pairs 最多 {PLAN_CHECK_PAIR_MAX} 对，当前 {len(pairs)} 对"
            )
        for plan_slot, check_slot in pairs:
            for slot, required in ((plan_slot, "plan_loop"), (check_slot, "key_insight_check")):
                if slot not in SLOTS:
                    raise ValueError(f"plan_check_pairs 引用了未知供应商槽 {slot}")
                if self.slot_api_key(slot) is None:
                    raise ValueError(f"plan_check_pairs 引用的 {slot} 没有 API key")
                if required not in getattr(self, f"{slot}_agents"):
                    raise ValueError(
                        f"plan_check_pairs 把 {required} 交给了 {slot}，"
                        f"但 {slot}_agents 里没有 {required}"
                    )

    def huggingface_hub_token(self) -> str | None:
        if self.hf_token is not None:
            return self.hf_token.get_secret_value()
        return os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")

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

    def plan_check_slot_pairs(self) -> tuple[tuple[SlotName, SlotName], ...]:
        raw = self.plan_check_pairs_spec.strip()
        if not raw:
            return ()
        return parse_plan_check_spec(raw)  # type: ignore[return-value]

    def plan_check_pairs(self) -> tuple[tuple[str, str], ...]:
        """Ordered (plan model, check model) pairs, one per parallel candidate path.

        With an explicit spec the pairs are taken in order. Exactly two pairs stay
        length two unless `plan_check_high_cross` is `ad` or `bc`, which appends a
        crossed third path for `high`. One pair stays length one, which makes `mid`
        and `high` unavailable rather than silently self-reviewing.
        """
        explicit = self.plan_check_slot_pairs()
        if explicit:
            pairs = [
                (self.slot_model(plan), self.slot_model(check))
                for plan, check in explicit
            ]
            if len(explicit) == 2 and self.plan_check_high_cross in {"ad", "bc"}:
                (plan_a, check_a), (plan_b, check_b) = explicit
                crossed = (
                    (plan_a, check_b)
                    if self.plan_check_high_cross == "ad"
                    else (plan_b, check_a)
                )
                pairs.append(
                    (self.slot_model(crossed[0]), self.slot_model(crossed[1]))
                )
            return tuple(pairs)

        groups = self.parallel_slots()
        if not groups:
            return ()
        n = len(groups)
        if n < 2:
            logger.warning(
                "plan/check 可用 slot 不足 2 个（当前 %s），high 模式会退化为同模型自审",
                n,
            )
        pairs = []
        for index in range(PLAN_CANDIDATE_MAX):
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

    def configured_slots(self) -> tuple[SlotName, ...]:
        return tuple(slot for slot in SLOTS if getattr(self, f"{slot}_agents"))

    def unrouted_agents(self) -> tuple[AgentName, ...]:
        routed = {
            agent
            for slot in SLOTS
            for agent in getattr(self, f"{slot}_agents")
        }
        return tuple(agent for agent in ALL_AGENTS if agent not in routed)

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

    def max_plan_candidates(self) -> int:
        """How many parallel candidate paths the current configuration supports."""
        return len(self.plan_check_pairs) or PLAN_CANDIDATE_MAX

    def plan_model_for_path(self, index: int) -> str:
        if self.plan_check_pairs:
            return self.plan_check_pairs[index][0]
        return self.model_for_agent("plan_loop")

    def check_model_for_path(self, index: int) -> str:
        if self.plan_check_pairs:
            return self.plan_check_pairs[index][1]
        return self.model_for_agent("key_insight_check")
