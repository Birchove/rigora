"""Schema-valid deterministic structured-model adapter."""

from pydantic import BaseModel

from research_mentor.agents.complete.contracts import CompleteAgentOutput
from research_mentor.agents.idea_review.contracts import IdeaReviewOutput, SearchPlan
from research_mentor.agents.plan_loop.contracts import PlanLoopOutput
from research_mentor.agents.working_qa.contracts import WorkingQAOutput
from research_mentor.domain.checks import KeyInsightCheckOutput
from research_mentor.domain.completion import ValidationCandidate
from research_mentor.domain.experiments import ExperimentInfo, ValidationTask
from research_mentor.domain.research import KeyInsight, KnowledgeItem, Milestone, ResearchPlan
from research_mentor.errors import PortExecutionError
from research_mentor.ports.model import ModelRequest, OutputT


def _plan() -> ResearchPlan:
    return ResearchPlan(
        research_question="分层状态压缩能否降低长对话恢复中的状态漂移？",
        knowledge_requirements=[KnowledgeItem(topic="状态恢复评估", reason="定义可复现实验指标")],
        milestones=[Milestone(name="基线与消融", goal="比较恢复正确率", estimated_duration="三天")],
        key_insight=KeyInsight(
            title="分层状态压缩",
            content="将稳定事实与近期交互分层保存并分别恢复。",
            rationale="减少无关上下文对恢复决策的干扰。",
        ),
    )


def _validation_candidate() -> ValidationCandidate:
    return ValidationCandidate(
        candidate_id="demo-validation-ablation",
        task=ValidationTask(
            paradigm="effectiveness",
            validation_type="ablation",
            name="移除分层摘要的消融实验",
            purpose="确认性能增益来自分层状态压缩",
            method="在同一任务集上移除分层摘要并比较恢复正确率",
            expected_result="完整方法的恢复正确率更高",
        ),
        priority="critical",
        rank=1,
        rationale="直接检验核心机制。",
        addresses_claims=["分层状态压缩降低状态漂移"],
    )


class DemoModelAdapter:
    """Return fixed fixtures selected by the requested production output schema."""

    def __init__(self) -> None:
        self.requests: list[ModelRequest[BaseModel]] = []

    async def generate(self, request: ModelRequest[OutputT]) -> OutputT:
        self.requests.append(request.model_copy(deep=True))
        output_name = request.output_model.__name__
        if output_name == SearchPlan.__name__:
            payload = SearchPlan(queries=["long context state compression recovery"])
        elif output_name == IdeaReviewOutput.__name__:
            payload = IdeaReviewOutput(
                idea_type="opinion",
                action="proceed_to_plan",
                normalized_idea="评估分层状态压缩对长对话恢复稳定性的作用",
                reason="研究问题明确、可验证且适合演示。",
                next_action="生成研究方案。",
            )
        elif output_name == PlanLoopOutput.__name__:
            payload = PlanLoopOutput(plan=_plan(), response_to_user="已生成可复现的演示方案。")
        elif output_name == KeyInsightCheckOutput.__name__:
            payload = {
                "assessment": {
                    "diagnostics": {
                        "core_claim": "分层状态压缩降低状态漂移",
                        "expected_contribution": "提升恢复正确率",
                        "validation_path": "基线、消融和重复运行",
                    },
                    "scores": {
                        name: {"score": 8, "reason": "演示 fixture 的固定评分"}
                        for name in (
                            "research_fit", "novelty", "research_value",
                            "testability_feasibility", "evidence_support",
                        )
                    },
                    "reason": "关键主张与验证路径一致。",
                    "summary_advice": "进入主实验。",
                },
                "final_score": 8,
                "check_decision": True,
                "decision_reason": "达到固定演示阈值。",
                "scoring_rule_version": "v1",
            }
        elif output_name == WorkingQAOutput.__name__:
            payload = WorkingQAOutput(
                action="answer",
                reason="问题与当前演示实验直接相关。",
                reply="先固定任务集与随机种子，再比较恢复正确率。",
                updated_experiment_info=ExperimentInfo(
                    current_experiment="比较分层压缩与完整历史基线"
                ),
            )
        elif output_name == CompleteAgentOutput.__name__:
            if "writing" in request.user_input.casefold():
                payload = CompleteAgentOutput(
                    mode="writing",
                    plan=_plan(),
                    final_hint="按证据强度组织结果。",
                    writing_guidance={
                        "suggested_structure": ["方法", "结果", "讨论"],
                        "key_results_to_report": ["恢复正确率与失败案例"],
                        "key_discussion_points": ["分层摘要的贡献"],
                        "limitations": ["演示数据不代表真实实验"],
                    },
                )
            else:
                payload = CompleteAgentOutput(
                    mode="validation",
                    plan=_plan(),
                    final_hint="请选择需要执行的验证实验。",
                    validation_candidates=[_validation_candidate()],
                )
        else:
            raise PortExecutionError(f"No demo fixture for output schema: {output_name}")
        return request.output_model.model_validate(payload)
