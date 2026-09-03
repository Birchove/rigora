"""Deterministic demo projects backed by production domain models and repositories."""

import asyncio
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from research_mentor.adapters.demo.retrieval import DemoRetrievalAdapter
from research_mentor.agents.complete.contracts import CompleteAgentOutput
from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.application.journal import ExportService
from research_mentor.domain.completion import ValidationCandidate, WritingGuidance
from research_mentor.domain.evidence import EvidenceRef, LiteratureRecord
from research_mentor.domain.experiments import (
    ExperimentInfo,
    ExperimentTaskContext,
    MainExperimentResult,
    ValidationTask,
)
from research_mentor.domain.projects import ResearchProject
from research_mentor.domain.research import (
    InitialInput,
    KeyInsight,
    KnowledgeItem,
    Milestone,
    ResearchContext,
    ResearchPlan,
)
from research_mentor.harness.phase import SessionPhase
from research_mentor.harness.state import ResearchSession, SessionEvent, SessionEventType
from research_mentor.harness.validation import ValidationQueue


DemoStage = Literal["submitted_idea", "working", "validation_selection"]
PublicDemoEventType = Literal[
    "command.accepted", "run.started", "agent.stage", "session.phase_changed"
]


class DemoEventStep(BaseModel):
    delay_ms: int = Field(ge=0)
    event_type: PublicDemoEventType
    payload: dict[str, str | int]


DEMO_EVENT_SCRIPT = (
    DemoEventStep(
        delay_ms=0,
        event_type="command.accepted",
        payload={"command_id": "demo-command", "run_id": "demo-run", "status": "queued"},
    ),
    DemoEventStep(
        delay_ms=120,
        event_type="run.started",
        payload={"run_id": "demo-run", "agent_name": "working_qa", "status": "running"},
    ),
    DemoEventStep(
        delay_ms=240,
        event_type="agent.stage",
        payload={"agent_name": "working_qa", "stage": "analysis", "status": "completed"},
    ),
    DemoEventStep(
        delay_ms=360,
        event_type="session.phase_changed",
        payload={"phase_before": "working", "phase_after": "awaiting_result_record"},
    ),
)


class DemoProject(BaseModel):
    project_id: str
    demo_stage: DemoStage
    phase: SessionPhase
    is_demo: bool
    visible_evidence: list[LiteratureRecord]
    latest_complete_output: CompleteAgentOutput | None = None
    validation_candidates: list[ValidationCandidate] = Field(default_factory=list)


_SEED_LOCK = asyncio.Lock()
_NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _idea() -> InitialInput:
    return InitialInput(
        original_idea="用分层状态压缩减少长对话恢复中的状态漂移",
        domain="computer_science",
        time_limit="两周",
        available_resources=["单张消费级 GPU", "固定对话任务集"],
    )


def _evidence() -> EvidenceRef:
    return EvidenceRef(
        source_id="demo-literature-state-compression",
        title="State Compression for Reliable Long-Context Recovery",
        authors=["Demo Research Group"],
        year=2026,
        source_type="paper",
        url="demo://literature/state-compression",
        support="用于演示状态压缩研究的证据引用 contract。",
    )


def _review() -> IdeaReviewOutput:
    return IdeaReviewOutput(
        idea_type="opinion",
        action="proceed_to_plan",
        normalized_idea="评估分层状态压缩对长对话恢复稳定性的作用",
        reason="研究问题明确、可验证且资源范围合理。",
        next_action="生成研究方案。",
        evidence=[_evidence()],
    )


def _plan() -> ResearchPlan:
    return ResearchPlan(
        research_question="分层状态压缩能否降低长对话恢复中的状态漂移？",
        knowledge_requirements=[
            KnowledgeItem(topic="状态恢复评估", reason="定义恢复正确率与漂移指标", references=[_evidence()])
        ],
        milestones=[
            Milestone(name="基线", goal="建立完整历史基线", estimated_duration="一天"),
            Milestone(name="主实验", goal="比较分层压缩的恢复正确率", estimated_duration="三天"),
        ],
        key_insight=KeyInsight(
            title="分层状态压缩",
            content="将稳定事实和近期交互分层保存并分别恢复。",
            rationale="减少无关上下文对恢复决策的干扰。",
            evidence=[_evidence()],
        ),
    )


def _candidate() -> ValidationCandidate:
    return ValidationCandidate(
        candidate_id="demo-validation-ablation",
        task=ValidationTask(
            paradigm="effectiveness",
            validation_type="ablation",
            name="移除分层摘要的消融实验",
            purpose="确认性能增益来自分层状态压缩",
            method="在相同任务和随机种子上移除分层摘要后比较恢复正确率",
            expected_result="完整方法的恢复正确率更高",
        ),
        priority="critical",
        rank=1,
        rationale="直接检验核心机制。",
        addresses_claims=["分层状态压缩降低状态漂移"],
    )


def _guidance() -> WritingGuidance:
    return WritingGuidance(
        suggested_structure=["问题与方法", "主实验结果", "验证与局限"],
        key_results_to_report=["恢复正确率", "状态漂移失败案例"],
        key_discussion_points=["分层摘要贡献与替代解释"],
        limitations=["当前为 deterministic demo fixture，不代表真实实验结果"],
    )


def _session(stage: DemoStage, session_id: str) -> ResearchSession:
    idea = _idea()
    review = _review()
    plan = _plan()
    common = {
        "session_id": session_id,
        "initial_input": idea,
        "idea_review": review,
    }
    if stage == "submitted_idea":
        return ResearchSession(phase=SessionPhase.PLANNING, **common)
    context = ResearchContext(
        normalized_idea=review.normalized_idea,
        research_question=plan.research_question,
        plan=plan,
    )
    task = ExperimentTaskContext(
        task_id="demo-main-task",
        task_kind="main",
        origin="plan",
        status="in_progress" if stage == "working" else "completed",
        experiment_info=ExperimentInfo(
            current_experiment="比较分层状态压缩与完整历史基线",
            expected_result="分层状态压缩具有更高恢复正确率",
            actual_result=None if stage == "working" else "恢复正确率从 0.71 提升至 0.82",
            observations=[] if stage == "working" else ["长对话后段的状态漂移减少"],
        ),
    )
    if stage == "working":
        return ResearchSession(
            phase=SessionPhase.WORKING,
            active_plan=plan,
            research_context=context,
            current_task=task,
            **common,
        )
    main_result = MainExperimentResult(
        execution_status="completed",
        impact="supports",
        objective="比较分层状态压缩与完整历史基线",
        method="固定任务、模型和随机种子，比较恢复正确率",
        expected_result="分层方法具有更高恢复正确率",
        actual_result="恢复正确率从 0.71 提升至 0.82",
        conclusion="主实验支持分层状态压缩，但仍需消融验证。",
    )
    candidate = _candidate()
    complete = CompleteAgentOutput(
        mode="validation",
        plan=plan,
        final_hint="请选择需要执行的验证实验。",
        validation_candidates=[candidate],
    )
    return ResearchSession(
        phase=SessionPhase.AWAITING_VALIDATION_SELECTION,
        active_plan=plan,
        research_context=context,
        current_task=task,
        main_experiment=main_result,
        latest_complete_output=complete,
        validation_queue=ValidationQueue.from_candidates([candidate]),
        writing_guidance=_guidance(),
        **common,
    )


_DEMO_PROJECTS: tuple[tuple[str, str, DemoStage], ...] = (
    ("demo-project-planning", "Demo：刚提交研究想法", "submitted_idea"),
    ("demo-project-working", "Demo：正在进行主实验", "working"),
    ("demo-project-validation", "Demo：选择补充验证", "validation_selection"),
)


class DemoService:
    def __init__(self, uow_factory, export_service: ExportService) -> None:
        self._uow_factory = uow_factory
        self._export_service = export_service
        self._retrieval = DemoRetrievalAdapter()

    async def ensure_seeded(self) -> list[DemoProject]:
        async with _SEED_LOCK:
            for index, (project_id, title, stage) in enumerate(_DEMO_PROJECTS):
                async with self._uow_factory() as uow:
                    if await uow.projects.get(project_id) is not None:
                        continue
                    session_id = f"demo-session-{index + 1}"
                    project = ResearchProject(
                        project_id=project_id,
                        title=title,
                        domain="computer_science",
                        session_id=session_id,
                        version=1,
                        is_demo=True,
                        created_at=_NOW,
                        updated_at=_NOW,
                    )
                    session = _session(stage, session_id)
                    await uow.projects.add(project)
                    await uow.sessions.add(session, project_id=project_id)
                    await uow.events.append(
                        SessionEvent(
                            event_id=f"demo-event-{index + 1}",
                            session_id=session_id,
                            event_type=SessionEventType.SESSION_CREATED,
                            phase_before=None,
                            phase_after=session.phase,
                            payload={"session_id": session_id},
                            occurred_at=_NOW.isoformat(),
                        )
                    )
                    records = await self._retrieval.search("state compression", limit=2)
                    await uow.literature.add_many(project_id, records, selected=True)
        return await self._snapshots()

    async def _snapshots(self) -> list[DemoProject]:
        snapshots = []
        for project_id, _, stage in _DEMO_PROJECTS:
            async with self._uow_factory() as uow:
                project = await uow.projects.get(project_id)
                if project is None:
                    continue
                session = await uow.sessions.get(project.session_id)
                evidence = await uow.literature.list_for_project(project_id)
            if session is None:
                continue
            output = session.latest_complete_output
            snapshots.append(
                DemoProject(
                    project_id=project_id,
                    demo_stage=stage,
                    phase=session.phase,
                    is_demo=project.is_demo,
                    visible_evidence=evidence,
                    latest_complete_output=output,
                    validation_candidates=(output.validation_candidates if output else []),
                )
            )
        return snapshots

    async def export(self, project_id: str, export_format: Literal["json", "md"]):
        journal = await self._export_service.build(project_id)
        if export_format == "json":
            return journal
        from research_mentor.application.journal import JournalRenderer

        return JournalRenderer().to_markdown(journal)


__all__ = ["DEMO_EVENT_SCRIPT", "DemoEventStep", "DemoProject", "DemoService"]
