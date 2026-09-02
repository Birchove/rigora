"""Contracts for the Idea Review Agent."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from research_mentor.agents.common import RetrievalSysInput
from research_mentor.domain.evidence import (
    EvidenceRef,
    LiteratureRecord,
    RetrievalDiagnostics,
)
from research_mentor.domain.research import ForwardResearchContext, InitialInput
from research_mentor.hyperparameters import SEARCH_PLAN_MAX_QUERIES

DEFAULT_IDEA_REVIEW_GUIDELINES = [
    "idea_review_agent 负责判断用户输入属于opinion、range 或 forward。对于 forward 类型，应进一步判断已有实验信息是否足以进入 Working 阶段：\n    - 信息充分：action = proceed_to_working\n    - 信息不足：action = request_refinement\n    experiment_in_progress 不要求 actual_result 或最终结论；缺少这些时应 proceed_to_working，不得因此 request_refinement，也不得编造实验结果。\n    Harness 不自行进行语义分类，只负责校验idea_type 与 action 的组合并执行状态路由。",
    "在不替用户决定核心研究主张的前提下形成规范化理解；range 类型只能整理为清晰的研究范围，不能由 Agent 擅自收敛成可通过的 Idea。",
    "分别评估研究问题的明确性、可验证性、研究价值、范围以及时间和资源可行性。",
    "range 表示用户仅提供了研究领域、宽泛主题或问题范围，尚未形成足够明确、可验证的研究 Idea。",
    "range 类型不得直接进入 ResearchPlan 阶段，必须输出 action = request_refinement。",
    "Agent 应明确指出当前输入缺少哪些形成研究 Idea 的关键要素，并提出少量、具体的澄清问题或候选聚焦方向，帮助用户形成明确的研究问题、研究主张或可验证目标。",
    "Agent 可以帮助用户聚焦，但不得替用户擅自决定最终 Idea。用户补充或确认后，应将新输入重新交给 idea_review_agent 审查。",
    "不得仅因 Idea 新颖而自动 Pass，也不得仅因已有相关研究而自动 Fail。",
    "已有相关研究与研究问题已经被充分解决是不同判断。",
    "Fail 表示当前状态不具备准入条件，不表示该方向永久没有研究价值。",
    "Pass 和 Fail 都必须给出明确 reason、有效 evidence 和可执行的 next_action。",
    "证据不足或检索失败时，不得编造确定性结论；应说明限制，并通过 next_action 告知用户需要补充什么。",
    "严格输出 IdeaReviewOutput，不生成完整 ResearchPlan，不设计完整实验，也不负责确定最终点睛之笔。",
]


class IdeaReviewSysInput(RetrievalSysInput):
    review_guidelines: list[str] = Field(
        default_factory=DEFAULT_IDEA_REVIEW_GUIDELINES.copy
    )


class IdeaReviewInput(BaseModel):
    idea: InitialInput
    sys_input: IdeaReviewSysInput
    literature_records: list[LiteratureRecord] = Field(default_factory=list)
    retrieval_diagnostics: list[RetrievalDiagnostics] = Field(default_factory=list)


SearchQuery = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class SearchPlan(BaseModel):
    queries: list[SearchQuery] = Field(min_length=1, max_length=SEARCH_PLAN_MAX_QUERIES)


class IdeaReviewOutput(BaseModel):
    idea_type: Literal["opinion", "range", "forward"]
    action: Literal[
        "proceed_to_plan",
        "proceed_to_working",
        "request_refinement",
        "reject",
    ]
    normalized_idea: str
    reason: str
    next_action: str
    literature_searches: list[LiteratureRecord] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    forward_context: ForwardResearchContext | None = None

    @model_validator(mode="after")
    def validate_route_payload(self) -> "IdeaReviewOutput":
        if self.idea_type == "range" and self.action != "request_refinement":
            raise ValueError("range can only request refinement")
        if self.action == "proceed_to_plan" and self.idea_type != "opinion":
            raise ValueError("only opinion can proceed to plan")
        if self.action == "proceed_to_working":
            if self.idea_type != "forward" or self.forward_context is None:
                raise ValueError(
                    "proceed_to_working requires forward idea and forward_context"
                )
            if self.forward_context.missing_fields:
                raise ValueError("proceed_to_working requires no missing fields")
        elif self.forward_context is not None:
            raise ValueError("only proceed_to_working can include forward_context")
        return self
