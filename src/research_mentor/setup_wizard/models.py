"""Typed panel request and response contracts."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from research_mentor.config import (
    ALL_AGENTS,
    PANEL_SLOTS,
    PLAN_CHECK_PAIR_MAX,
    SHARED_AGENTS,
    SLOTS,
    AgentName,
    SlotName,
    VendorApiStyle,
)
from research_mentor.hyperparameters import PLAN_CANDIDATE_COUNTS


EXCLUSIVE_AGENTS: tuple[AgentName, ...] = tuple(
    agent for agent in ALL_AGENTS if agent not in SHARED_AGENTS
)


class SlotConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot: SlotName
    # 可能是明文、空串（保持不变）或 KEEP_SENTINEL；解析在 apply 层做。
    api_key: str = ""
    base_url: str = ""
    model: str = Field(default="", max_length=200)
    api_style: VendorApiStyle = "chat_completions"

    @model_validator(mode="after")
    def validate_required_text(self) -> Self:
        if not self.model.strip():
            raise ValueError(f"{self.slot} 缺少模型名")
        if self.api_style == "chat_completions" and not self.base_url.strip():
            raise ValueError(f"{self.slot} 使用 chat_completions 时必须提供 base_url")
        return self


class OptionalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    openalex_api_key: str = ""
    hf_token: str = ""
    hf_endpoint: str = ""
    database_url: str = ""
    reranker_backend: str = "auto"


class PlanCheckPair(BaseModel):
    """One parallel candidate path: `plan` proposes, `check` scores."""

    model_config = ConfigDict(extra="forbid")

    plan: SlotName
    check: SlotName


class ProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot: SlotName
    api_key: str = ""
    base_url: str = ""
    model: str = Field(default="", max_length=200)
    api_style: VendorApiStyle = "chat_completions"

    @model_validator(mode="after")
    def validate_panel_slot(self) -> Self:
        if self.slot not in PANEL_SLOTS:
            raise ValueError(f"面板不支持这个供应商槽: {self.slot}")
        return self


class ProbeResult(BaseModel):
    ok: bool
    message: str


class SaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slots: list[SlotConfig] = Field(min_length=1)
    # 只覆盖独占 Agent；plan_loop 与 key_insight_check 由 pairs 决定。
    assignments: dict[AgentName, list[SlotName]]
    pairs: list[PlanCheckPair] = Field(min_length=1, max_length=PLAN_CHECK_PAIR_MAX)
    high_cross: Literal["off", "ad", "bc"] = "off"
    optional: OptionalConfig = Field(default_factory=OptionalConfig)

    @model_validator(mode="after")
    def validate_coverage(self) -> Self:
        chosen = [item.slot for item in self.slots]
        if len(chosen) != len(set(chosen)):
            raise ValueError("同一个供应商重复提交")
        outside = [slot for slot in chosen if slot not in PANEL_SLOTS]
        if outside:
            raise ValueError("面板不支持这些供应商槽: " + ", ".join(outside))
        available = set(chosen)

        missing = [
            agent for agent in EXCLUSIVE_AGENTS if agent not in self.assignments
        ]
        if missing:
            raise ValueError("以下 Agent 未分配模型: " + ", ".join(missing))
        extra = [agent for agent in self.assignments if agent in SHARED_AGENTS]
        if extra:
            raise ValueError(
                "方案生成与点睛之笔评分请通过 pairs 配置，不要放进 assignments"
            )

        for agent, slots in self.assignments.items():
            if len(slots) != 1:
                raise ValueError(f"{agent} 只能由一个供应商承担")
            if slots[0] not in available:
                raise ValueError(f"{agent} 指向了未配置的供应商: {slots[0]}")

        seen: set[tuple[str, str]] = set()
        for pair in self.pairs:
            for slot in (pair.plan, pair.check):
                if slot not in available:
                    raise ValueError(f"配对引用了未配置的供应商: {slot}")
            key = (pair.plan, pair.check)
            if key in seen:
                raise ValueError(f"配对 {pair.plan}>{pair.check} 重复")
            seen.add(key)
        return self

    def slot_agents(self) -> dict[SlotName, list[AgentName]]:
        """Which agents each slot ends up serving, in canonical agent order."""
        mapping: dict[SlotName, list[AgentName]] = {
            item.slot: [] for item in self.slots
        }
        for agent in EXCLUSIVE_AGENTS:
            for slot in self.assignments.get(agent, []):
                mapping[slot].append(agent)
        for pair in self.pairs:
            mapping[pair.plan].append("plan_loop")
            mapping[pair.check].append("key_insight_check")
        return {
            slot: [agent for agent in ALL_AGENTS if agent in set(agents)]
            for slot, agents in mapping.items()
        }

    def parallel_path_count(self) -> int:
        """Paths available at runtime; mirrors `Settings.plan_check_pairs()`."""
        if len(self.pairs) == 2 and self.high_cross in {"ad", "bc"}:
            return 3
        return len(self.pairs)

    def available_modes(self) -> list[str]:
        paths = self.parallel_path_count()
        return [
            mode for mode, needed in PLAN_CANDIDATE_COUNTS.items() if needed <= paths
        ]


class SlotState(BaseModel):
    slot: SlotName
    has_key: bool
    masked_key: str
    base_url: str
    model: str
    api_style: str
    agents: list[str]


class OptionalState(BaseModel):
    openalex_has_key: bool
    openalex_masked: str
    hf_has_token: bool
    hf_masked: str
    hf_endpoint: str
    database_has_url: bool
    database_masked: str
    reranker_backend: str


class CurrentConfig(BaseModel):
    env_exists: bool
    env_path: str
    slots: list[SlotState]
    pairs: list[PlanCheckPair]
    high_cross: str
    optional: OptionalState

    @staticmethod
    def slot_names() -> tuple[SlotName, ...]:
        return SLOTS
