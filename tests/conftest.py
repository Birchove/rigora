from datetime import date

import pytest

from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.agents.plan_loop.contracts import PlanLoopOutput, PlanLoopSysInput
from research_mentor.config import HarnessConfig
from research_mentor.domain.checks import (
    DimensionScore,
    KeyInsightAssessment,
    KeyInsightCheckOutput,
    KeyInsightDiagnostics,
    KeyInsightScores,
)
from research_mentor.domain.research import (
    InitialInput,
    KeyInsight,
    KnowledgeItem,
    Milestone,
    ResearchPlan,
    UserPlanFeedback,
)
from research_mentor.harness.scoring import finalize_key_insight_check


@pytest.fixture(autouse=True)
def clear_vendor_settings_environment(monkeypatch):
    for name in (
        "RESEARCH_MENTOR_QWEN_API_KEY",
        "RESEARCH_MENTOR_QWEN_BASE_URL",
        "RESEARCH_MENTOR_QWEN_MODEL",
        "RESEARCH_MENTOR_QWEN_API_STYLE",
        "RESEARCH_MENTOR_QWEN_AGENTS",
        "RESEARCH_MENTOR_DEEPSEEK_API_KEY",
        "RESEARCH_MENTOR_DEEPSEEK_BASE_URL",
        "RESEARCH_MENTOR_DEEPSEEK_MODEL",
        "RESEARCH_MENTOR_DEEPSEEK_API_STYLE",
        "RESEARCH_MENTOR_DEEPSEEK_AGENTS",
        "RESEARCH_MENTOR_CHATGPT_API_KEY",
        "RESEARCH_MENTOR_CHATGPT_BASE_URL",
        "RESEARCH_MENTOR_CHATGPT_MODEL",
        "RESEARCH_MENTOR_CHATGPT_API_STYLE",
        "RESEARCH_MENTOR_CHATGPT_AGENTS",
        "RESEARCH_MENTOR_CHATGPT_2_API_KEY",
        "RESEARCH_MENTOR_CHATGPT_2_BASE_URL",
        "RESEARCH_MENTOR_CHATGPT_2_MODEL",
        "RESEARCH_MENTOR_CHATGPT_2_API_STYLE",
        "RESEARCH_MENTOR_CHATGPT_2_AGENTS",
        "RESEARCH_MENTOR_GLM_API_KEY",
        "RESEARCH_MENTOR_GLM_BASE_URL",
        "RESEARCH_MENTOR_GLM_MODEL",
        "RESEARCH_MENTOR_GLM_API_STYLE",
        "RESEARCH_MENTOR_GLM_AGENTS",
        "RESEARCH_MENTOR_VENDOR",
        "RESEARCH_MENTOR_DEFAULT_MODEL",
        "RESEARCH_MENTOR_AGENT_IDEA_REVIEW_MODEL",
        "RESEARCH_MENTOR_AGENT_PLAN_LOOP_MODEL",
        "RESEARCH_MENTOR_AGENT_KEY_INSIGHT_CHECK_MODEL",
        "RESEARCH_MENTOR_AGENT_WORKING_QA_MODEL",
        "RESEARCH_MENTOR_AGENT_COMPLETE_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def initial_input() -> InitialInput:
    return InitialInput(
        original_idea="用状态压缩减少长对话恢复中的状态漂移",
        domain="computer science",
        time_limit="两周",
    )


@pytest.fixture
def key_insight() -> KeyInsight:
    return KeyInsight(
        title="分层状态压缩",
        content="比较分层状态压缩与基线恢复正确率。",
        rationale="减少无关上下文有助于稳定恢复。",
    )


@pytest.fixture
def research_plan(key_insight: KeyInsight) -> ResearchPlan:
    return ResearchPlan(
        research_question="分层状态压缩能否提升长对话恢复正确率？",
        knowledge_requirements=[KnowledgeItem(topic="状态管理", reason="定义比较基线")],
        milestones=[Milestone(name="基线", goal="测量恢复正确率", estimated_duration="三天")],
        key_insight=key_insight,
    )


@pytest.fixture
def review_output() -> IdeaReviewOutput:
    return IdeaReviewOutput(
        idea_type="opinion",
        action="proceed_to_plan",
        normalized_idea="评估状态压缩对长对话恢复稳定性的作用",
        reason="研究主张可验证。",
        next_action="制定研究方案。",
    )


@pytest.fixture
def plan_output(research_plan: ResearchPlan) -> PlanLoopOutput:
    return PlanLoopOutput(
        plan=research_plan,
        response_to_user="方案围绕恢复正确率设计。",
    )


@pytest.fixture
def assessment() -> KeyInsightAssessment:
    scores = KeyInsightScores(
        **{
            name: DimensionScore(score=7.0, reason=f"{name} reason")
            for name in (
                "research_fit",
                "novelty",
                "research_value",
                "testability_feasibility",
                "evidence_support",
            )
        }
    )
    return KeyInsightAssessment(
        diagnostics=KeyInsightDiagnostics(
            core_claim="状态压缩提升恢复稳定性",
            expected_contribution="降低长对话状态漂移",
            validation_path="比较恢复正确率",
        ),
        scores=scores,
        reason="总体判断",
        summary_advice="保持验证路径聚焦",
    )


@pytest.fixture
def check_output(assessment: KeyInsightAssessment) -> KeyInsightCheckOutput:
    return finalize_key_insight_check(assessment, HarnessConfig())


@pytest.fixture
def user_feedback() -> UserPlanFeedback:
    return UserPlanFeedback(user_reason="缩小实验范围")


@pytest.fixture
def plan_sys_input() -> PlanLoopSysInput:
    return PlanLoopSysInput(current_date=date(2026, 8, 29))
