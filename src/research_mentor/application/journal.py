"""Canonical structured research journal and deterministic exports."""

from datetime import datetime, timezone
import json

from pydantic import BaseModel, Field

from research_mentor.agents.complete.contracts import CompleteAgentOutput
from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.agents.plan_loop.contracts import PlanLoopOutput
from research_mentor.domain.checks import KeyInsightCheckOutput
from research_mentor.domain.completion import WritingGuidance
from research_mentor.domain.evidence import LiteratureRecord
from research_mentor.domain.experiments import ExperimentTaskContext, MainExperimentResult, ValidationResult
from research_mentor.domain.projects import ResearchProject
from research_mentor.domain.research import (
    InitialInput,
    OverrideRecord,
    PlanCandidateOverrideRecord,
    UserPlanDecision,
)
from research_mentor.harness.state import PlanRevisionRecord
from research_mentor.application.views import ProjectNotFoundError


class ResearchJournal(BaseModel):
    project: ResearchProject
    initial_input: InitialInput | None = None
    idea_review: IdeaReviewOutput | None = None
    literature: list[LiteratureRecord] = Field(default_factory=list)
    plans: list[PlanLoopOutput] = Field(default_factory=list)
    checks: list[KeyInsightCheckOutput] = Field(default_factory=list)
    plan_decisions: list[UserPlanDecision] = Field(default_factory=list)
    override_records: list[OverrideRecord | PlanCandidateOverrideRecord] = Field(default_factory=list)
    plan_revision_records: list[PlanRevisionRecord] = Field(default_factory=list)
    experiment_tasks: list[ExperimentTaskContext] = Field(default_factory=list)
    main_result: MainExperimentResult | None = None
    validation_results: list[ValidationResult] = Field(default_factory=list)
    complete_outputs: list[CompleteAgentOutput] = Field(default_factory=list)
    writing_guidance: WritingGuidance | None = None
    generated_at: datetime


class JournalRenderer:
    @staticmethod
    def _json(value: BaseModel) -> str:
        return json.dumps(value.model_dump(mode="json"), ensure_ascii=False, indent=2)

    def to_markdown(self, journal: ResearchJournal) -> str:
        parts = [f"# {journal.project.title}", "", "## 研究想法"]
        parts.append(self._json(journal.initial_input) if journal.initial_input else "尚未提交。")
        if journal.idea_review:
            parts.extend(["", "### Idea Review", self._json(journal.idea_review)])

        parts.extend(["", "## 证据"])
        if journal.literature:
            for item in journal.literature:
                provider = f"（{item.provider}）" if item.provider else ""
                parts.extend([f"### {item.title}{provider}", item.summary, f"相关性：{item.relevance}"])
        else:
            parts.append("暂无结构化文献记录。")

        parts.extend(["", "## Plan / Check 争论"])
        for index, plan in enumerate(journal.plans, 1):
            parts.extend([f"### Plan {index}", self._json(plan)])
        for index, check in enumerate(journal.checks, 1):
            parts.extend([f"### Check {index}", self._json(check)])
        for decision in journal.plan_decisions:
            parts.extend(["### 用户决策", self._json(decision)])
        for record in journal.override_records:
            parts.extend(["### Override", self._json(record)])
        for record in journal.plan_revision_records:
            parts.extend(["### Plan revision", self._json(record)])

        parts.extend(["", "## 实验任务"])
        parts.extend(self._json(task) for task in journal.experiment_tasks)
        parts.extend(["", "## 实验结果"])
        parts.append(self._json(journal.main_result) if journal.main_result else "尚无主实验结果。")

        parts.extend(["", "## Validation"])
        parts.extend(self._json(result) for result in journal.validation_results)
        if not journal.validation_results:
            parts.append("暂无 validation 结果。")

        parts.extend(["", "## WritingGuidance"])
        parts.append(self._json(journal.writing_guidance) if journal.writing_guidance else "尚未生成写作指导。")
        parts.extend(["", f"生成时间：{journal.generated_at.isoformat()}"])
        return "\n\n".join(parts) + "\n"


class ExportService:
    def __init__(self, uow_factory, *, now=None) -> None:
        self._uow_factory = uow_factory
        self._now = now or (lambda: datetime.now(timezone.utc))

    async def build(self, project_id: str) -> ResearchJournal:
        async with self._uow_factory() as uow:
            project = await uow.projects.get(project_id)
            if project is None:
                raise ProjectNotFoundError(project_id)
            session = await uow.sessions.get(project.session_id)
            if session is None:
                raise ProjectNotFoundError(project_id)
            literature = await uow.literature.list_for_project(project_id)
        tasks = [session.current_task] if session.current_task is not None else []
        candidate_plans = [
            PlanLoopOutput(
                plan=candidate.plan,
                response_to_user=candidate.response_to_user or "候选方案",
                change_summary=candidate.change_summary,
            )
            for candidate in session.plan_candidates
            if candidate.plan is not None
        ]
        plans = candidate_plans or ([session.latest_plan_output] if session.latest_plan_output else [])
        candidate_checks = [
            round_.output
            for candidate in session.plan_candidates
            for round_ in candidate.check_history
        ]
        checks = candidate_checks or ([session.latest_check] if session.latest_check else [])
        overrides = list(session.candidate_override_records)
        if session.override_record is not None:
            overrides.append(session.override_record)
        return ResearchJournal(
            project=project,
            initial_input=session.initial_input,
            idea_review=session.idea_review,
            literature=literature,
            plans=plans,
            checks=checks,
            plan_decisions=[session.plan_decision] if session.plan_decision else [],
            override_records=overrides,
            plan_revision_records=session.plan_revision_records,
            experiment_tasks=tasks,
            main_result=session.main_experiment,
            validation_results=session.completed_validations,
            complete_outputs=[session.latest_complete_output] if session.latest_complete_output else [],
            writing_guidance=session.writing_guidance,
            generated_at=self._now(),
        )
