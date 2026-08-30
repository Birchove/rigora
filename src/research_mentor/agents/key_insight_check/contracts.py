"""Contracts for the Key Insight Check Agent."""

from pydantic import BaseModel, Field

from research_mentor.agents.common import SysInput
from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.agents.plan_loop.contracts import PlanLoopOutput
from research_mentor.domain.checks import KeyInsightAssessment, KeyInsightCheckOutput
from research_mentor.domain.research import InitialInput, ResearchPlan

DEFAULT_CHECK_GUIDELINES = [
    "check_guidelines 只用于追加当前轮的特殊检查关注点，不得复制或重写固定评分维度、权重和通过阈值。",
    "额外规则不得要求 key_insight_check_agent 重写 ResearchPlan、生成新的 KeyInsight 或修改用户研究目标。",
    "额外规则与固定 Check Prompt 或 Harness 决策规则冲突时，以固定 Prompt 和版本化 Harness 规则为准。",
]


class KeyInsightCheckSysInput(SysInput):
    check_guidelines: list[str] = Field(default_factory=DEFAULT_CHECK_GUIDELINES.copy)


class KeyInsightCheckInput(BaseModel):
    idea: InitialInput
    sys_input: KeyInsightCheckSysInput
    review_result: IdeaReviewOutput
    key_insight_input: PlanLoopOutput
    plan: ResearchPlan
    previous_check_feedback: str | None = None
