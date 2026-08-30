"""Contracts for the Plan Loop Agent."""

from typing import Self

from pydantic import BaseModel, Field, model_validator

from research_mentor.agents.common import SysInput
from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.domain.checks import KeyInsightCheckOutput
from research_mentor.domain.research import InitialInput, ResearchPlan, UserPlanFeedback

DEFAULT_PLANNING_GUIDELINES = [
    "ResearchPlan 必须直接服务于 normalized_idea，不得擅自改变用户已经确认的核心研究目标。",
    "research_question 必须聚焦、可验证，并能够在用户的时间、资源和知识条件下执行。",
    "knowledge_requirements 只保留完成当前研究真正需要的内容；每项必须说明学习原因，外部事实应附有效 EvidenceRef。",
    "milestones 应按合理依赖顺序排列，每项具有明确目标和现实的 estimated_duration。",
    "KeyInsight 必须说明具体增量、成立理由及可验证路径，不得只更换术语、堆叠模块或使用空泛创新表述。",
    "时间、资源或证据不足时，将未确定事项写入 open_issues，不得用假设填补缺失信息。",
    "收到 previous_insight_check 时，只处理 revision_request 指向的问题，同时保持方案其余部分稳定。",
    "收到 user_feedback 时，判断其合理性后再修改方案，不得无条件接受或机械拒绝。",
    "每轮只做解决当前反馈所需的最小修改，并通过 change_summary 记录相对上一版的实际变化。",
]

DEFAULT_INTERACTION_GUIDELINES = [
    "首次生成方案时，response_to_user 应概括研究问题、实施路径、KeyInsight 和仍待确认事项。",
    "user_feedback 不为空时，必须直接回应 user_reason，并说明接受、部分接受或不接受的具体理由。",
    "接受用户意见时，在 change_summary 中记录对应修改；未修改的内容不得写入 change_summary。",
    "部分接受或不接受用户意见时，在 response_to_user 中给出与研究目标、证据或现实约束相关的理由。",
    "保持严格、专业、建设性；不得为了维持导师人设刻意制造分歧。",
    "不得声称方案已经得到用户确认；最终 accept、request_revision 或 override 由 Harness 的 UserPlanDecision gate 处理。",
]


class PlanLoopSysInput(SysInput):
    planning_guidelines: list[str] = Field(default_factory=DEFAULT_PLANNING_GUIDELINES.copy)
    interaction_guidelines: list[str] = Field(default_factory=DEFAULT_INTERACTION_GUIDELINES.copy)


class PlanLoopInput(BaseModel):
    idea: InitialInput
    sys_input: PlanLoopSysInput
    review_result: IdeaReviewOutput
    loop_round: int = 5
    previous_insight_check: KeyInsightCheckOutput | None = None
    previous_plan: ResearchPlan | None = None
    user_feedback: UserPlanFeedback | None = None

    @model_validator(mode="after")
    def validate_mode(self) -> Self:
        presence = (
            self.previous_plan is not None,
            self.previous_insight_check is not None,
            self.user_feedback is not None,
        )
        if presence not in ((False, False, False), (True, True, False), (True, False, True)):
            raise ValueError("PlanLoopInput 的修订输入组合无效")
        return self


class PlanLoopOutput(BaseModel):
    plan: ResearchPlan
    change_summary: list[str] = Field(default_factory=list)
    response_to_user: str
