"""Contracts for the Working QA Agent."""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from research_mentor.agents.common import SysInput
from research_mentor.domain.evidence import EvidenceRef
from research_mentor.domain.experiments import ExperimentInfo, ExperimentTaskContext
from research_mentor.domain.research import InitialInput, ResearchPlan

DEFAULT_QA_GUIDELINES = [
    "只回答与 normalized_idea、ResearchPlan 或 task_context 指定的当前实验任务直接相关的问题。",
    "task_context 中的 task_id、task_kind、origin、status、parent_task_id 和 validation_task 由 Harness 管理；不得建议或声称已经修改这些字段。",
    "信息足以回答时使用 answer；只缺少少量关键事实时使用 clarify，并只询问继续判断所需的最少信息。",
    "问题与当前研究无关、超出职责边界或无法在有效信息和证据基础上回答时使用 decline，并说明边界。",
    "只有用户输入和实验记录足以表明当前实验任务已经完成时才使用 success；success 不代表整个科研流程结束。",
    "success 时必须返回包含当前实验最终事实的完整 updated_experiment_info。",
    "比较 expected_result 与 actual_result 时，应区分观察事实、合理推断和未知原因，不得把相关性写成因果结论。",
    "updated_experiment_info 必须是合并本轮可靠新增或修正信息后的完整快照，不得编造、覆盖或美化实验结果。",
    "用户明确修正旧实验信息时，可以使用新信息替代旧值，但必须在 reason 中说明修正依据。",
    "发现结果与预期不一致时，给出优先级明确且可验证的排查建议，不得一次扩展成新的完整研究方案。",
    "实验顺利完成但结果不支持预期，不等于执行失败；必须如实保留负面、不显著和不确定结果。",
    "不负责决定补充实验是否齐全，也不负责论文写作；这些任务属于 complete_agent。",
    "引用 EvidenceRef 时必须说明其具体支持的判断；没有外部证据时明确说明限制。",
]


class WorkingQASysInput(SysInput):
    qa_guidelines: list[str] = Field(default_factory=DEFAULT_QA_GUIDELINES.copy)


class WorkingQAInput(BaseModel):
    idea: InitialInput
    question: str
    sys_input: WorkingQASysInput
    normalized_idea: str
    plan: ResearchPlan
    task_context: ExperimentTaskContext
    compact_context: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_active_task(self) -> Self:
        if self.task_context.status != "in_progress":
            raise ValueError("只有 status = in_progress 的任务可以调用 working_qa_agent")
        current_experiment = self.task_context.experiment_info.current_experiment
        if current_experiment is None or not current_experiment.strip():
            raise ValueError("调用 working_qa_agent 前，Harness 必须初始化 current_experiment")
        return self


class WorkingQAOutput(BaseModel):
    action: Literal["answer", "clarify", "decline", "success"]
    reason: str
    reply: str
    updated_experiment_info: ExperimentInfo | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_action_fields(self) -> Self:
        if self.action == "success":
            if self.reply != "":
                raise ValueError("success 时 reply 必须为空字符串")
            if self.updated_experiment_info is None:
                raise ValueError("success 时必须返回完整的 updated_experiment_info")
            actual_result = self.updated_experiment_info.actual_result
            if actual_result is None or not actual_result.strip():
                raise ValueError("success 时 actual_result 不能为空")
        elif not self.reply.strip():
            raise ValueError("非 success 状态必须提供 reply")
        return self
