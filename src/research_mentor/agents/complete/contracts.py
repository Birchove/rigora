"""Contracts for the Complete Agent."""

from pydantic import BaseModel, Field, model_validator

from research_mentor.agents.common import SysInput
from research_mentor.domain.completion import CompleteAgentOutput
from research_mentor.domain.experiments import MainExperimentResult, ValidationResult
from research_mentor.domain.research import InitialInput, ResearchContext, ResearchPlan

DEFAULT_VALIDATION_GUIDELINES = [
    "根据 ResearchPlan、KeyInsight、主实验结果和 completed_validations 判断当前证据链仍缺少哪些验证。",
    "只建议能够检验关键主张、排除主要替代解释或补足可靠性风险的实验，不得为了显得完整而堆叠实验。",
    "建议必须符合用户时间、数据、算力、设备和知识条件；不可执行的实验应明确排除或降级。",
    "不得重复已经完成且结论充分的 ValidationTask；应利用所有 completed_validations，包括未支持预期的结果。",
    "实验顺利完成但结果不支持假设，不等于执行失败；必须保留负面或不确定结果并说明其影响。",
    "不得在实验尚未返回 ValidationResult 时将其视为完成，也不得编造 actual_result、conclusion 或 evidence_files。",
    "如果现有结果动摇主结论或 KeyInsight，应明确指出需要修订 ResearchPlan，而不是跳过反对证据。",
    "补充实验建议应给出目的、方法、预期观察和优先级，并优先处理对核心结论影响最大的缺口。",
]

DEFAULT_WRITING_GUIDELINES = [
    "只提供论文结构、结果组织、讨论重点和局限性指导，不直接生成完整论文。",
    "只报告 MainExperimentResult 和 completed_validations 中实际存在的结果，不得补写或美化数据。",
    "清楚区分实验结果、作者解释、证据支持的推断和仍然未知的内容。",
    "核心结论的强度不得超过现有证据；负面、不显著和不确定结果也应如实呈现。",
    "必须指出研究局限、潜在混杂因素、有效性威胁和未完成验证，不得为了叙事完整而省略。",
    "写作建议应围绕 research_question 和 KeyInsight 组织，并说明每项关键结果适合放入的章节。",
    "涉及文献时仅使用已有有效 EvidenceRef，不得生成不存在的题名、作者、DOI 或 URL。",
    "final_hint 应具体、可执行并适合用户直接用于下一步写作规划。",
]


class CompleteAgentSysInput(SysInput):
    completion_status: bool
    validation_guidelines: list[str] = Field(default_factory=DEFAULT_VALIDATION_GUIDELINES.copy)
    writing_guidelines: list[str] = Field(default_factory=DEFAULT_WRITING_GUIDELINES.copy)


class CompleteAgentInput(BaseModel):
    idea: InitialInput
    normalized_idea: str
    sys_input: CompleteAgentSysInput
    research_context: ResearchContext | None = None
    plan: ResearchPlan | None = None
    main_experiment: MainExperimentResult
    completed_validations: list[ValidationResult] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_research_source(self):
        if self.plan is None:
            if self.research_context is None or self.research_context.forward_context is None:
                raise ValueError("planless completion requires forward research context")
        return self
