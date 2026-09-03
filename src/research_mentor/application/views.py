"""Project creation and server-authoritative frontend views."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from research_mentor.application.allowed_commands import allowed_commands
from research_mentor.domain.completion import ValidationCandidate, WritingGuidance
from research_mentor.domain.evidence import LiteratureRecord
from research_mentor.domain.experiments import ExperimentTaskContext, ValidationTask
from research_mentor.domain.jobs import AgentRun
from research_mentor.domain.projects import ResearchProject
from research_mentor.harness.phase import SessionPhase
from research_mentor.harness.session_slices import PendingWorkingClarification
from research_mentor.harness.state import (
    ResearchSession,
    SessionEvent,
    SessionEventType,
)
from research_mentor.hyperparameters import MAX_CHECK_ROUNDS
from research_mentor.ports.events import OutboxEvent, PersistedPublicEvent


class ActiveRunView(BaseModel):
    run_id: str
    agent_name: str
    status: str
    public_message: str | None = None


class VisibleEvidenceItem(BaseModel):
    title: str
    source_type: str = "other"
    url: str | None = None
    summary: str | None = None
    support: str | None = None
    selected: bool = True


class StageProgress(BaseModel):
    headline: str
    detail: str | None = None
    check_round: int = 0
    max_check_rounds: int = MAX_CHECK_ROUNDS
    candidate_count: int = 0
    idea_type: str | None = None
    idea_action: str | None = None
    idea_reason: str | None = None
    normalized_idea: str | None = None
    plan_question: str | None = None
    key_insight_title: str | None = None
    last_check_score: float | None = None
    last_check_passed: bool | None = None


class PublicActivityItem(BaseModel):
    sequence: int
    type: str
    summary: str


class PlanCandidateView(BaseModel):
    candidate_id: str
    disposition: str
    focus_hint: str = ""
    check_round: int = 0
    research_question: str | None = None
    key_insight_title: str | None = None
    key_insight_content: str | None = None


class CurrentTaskView(BaseModel):
    task_id: str
    task_kind: str
    origin: str
    status: str
    current_experiment: str | None = None
    expected_result: str | None = None
    validation_task: ValidationTask | None = None


class WorkingTurnView(BaseModel):
    question: str = ""
    action: str
    reply: str
    reason: str = ""
    occurred_at: str | None = None


class ProjectView(BaseModel):
    project_id: str
    title: str
    domain: str
    version: int = Field(ge=1)
    phase: SessionPhase
    is_demo: bool = False
    allowed_commands: list[str]
    last_event_sequence: int = 0
    active_run: ActiveRunView | None = None
    validation_candidates: list[ValidationCandidate] = Field(default_factory=list)
    visible_evidence: list[VisibleEvidenceItem] = Field(default_factory=list)
    stage_progress: StageProgress | None = None
    recent_activity: list[PublicActivityItem] = Field(default_factory=list)
    plan_candidates: list[PlanCandidateView] = Field(default_factory=list)
    current_task: CurrentTaskView | None = None
    writing_guidance: WritingGuidance | None = None
    revision_reason: str | None = None
    working_turns: list[WorkingTurnView] = Field(default_factory=list)
    pending_clarification: PendingWorkingClarification | None = None


class ProjectNotFoundError(Exception):
    pass


class UnsupportedDomainError(Exception):
    pass


class ProjectViewService:
    def __init__(
        self,
        uow_factory,
        *,
        supported_domains: tuple[str, ...],
        supported_domain_aliases: tuple[str, ...],
        new_id: Callable[[], str] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._new_id = new_id or (lambda: str(uuid4()))
        self._now = now or (lambda: datetime.now(timezone.utc))
        canonical = supported_domains[0]
        self._domains = {
            value.strip().casefold(): canonical
            for value in (*supported_domains, *supported_domain_aliases)
        }

    async def create(self, *, title: str, domain: str) -> ProjectView:
        normalized_domain = self._domains.get(domain.strip().casefold())
        if normalized_domain is None:
            raise UnsupportedDomainError(domain)
        project_id = self._new_id()
        session_id = self._new_id()
        event_id = self._new_id()
        occurred_at = self._now()
        project = ResearchProject(
            project_id=project_id,
            title=title,
            domain=normalized_domain,
            session_id=session_id,
            version=1,
            created_at=occurred_at,
            updated_at=occurred_at,
        )
        session = ResearchSession(session_id=session_id)
        event = SessionEvent(
            event_id=event_id,
            session_id=session_id,
            event_type=SessionEventType.SESSION_CREATED,
            phase_before=None,
            phase_after=SessionPhase.AWAITING_IDEA,
            payload={},
            occurred_at=occurred_at.isoformat(),
        )
        async with self._uow_factory() as uow:
            await uow.projects.add(project)
            await uow.sessions.add(session, project_id=project_id)
            await uow.events.append(event)
            await uow.outbox.append(
                OutboxEvent(
                    outbox_id=self._new_id(),
                    session_event_id=event_id,
                    project_id=project_id,
                    topic="session.created",
                    payload={"session_id": session_id},
                    created_at=occurred_at,
                )
            )
        return await self.get(project_id)

    async def get(self, project_id: str) -> ProjectView:
        async with self._uow_factory() as uow:
            project = await uow.projects.get(project_id)
            if project is None:
                raise ProjectNotFoundError(project_id)
            session = await uow.sessions.get(project.session_id)
            if session is None:
                raise ProjectNotFoundError(project_id)
            active_run = await uow.runs.find_active_for_project(project_id)
            last_event_sequence = await uow.events.latest_sequence(project_id)
            literature = await uow.literature.list_for_project(project_id)
            events = await uow.events.list_for_project_after(project_id, after=0)
        return self._to_view(
            project,
            session,
            active_run=active_run,
            last_event_sequence=last_event_sequence,
            literature=literature,
            events=events,
        )

    async def list(self) -> list[ProjectView]:
        async with self._uow_factory() as uow:
            projects = await uow.projects.list()
            views = []
            for project in projects:
                session = await uow.sessions.get(project.session_id)
                if session is None:
                    continue
                # Sidebar projection: title/phase/normalized_idea live on the
                # session. Skip per-project run/literature/event scans.
                views.append(
                    self._to_view(
                        project,
                        session,
                        active_run=None,
                        last_event_sequence=0,
                        literature=[],
                        events=[],
                    )
                )
        return views

    @staticmethod
    def _to_view(
        project: ResearchProject,
        session: ResearchSession,
        *,
        active_run: AgentRun | None,
        last_event_sequence: int,
        literature: list[LiteratureRecord],
        events: list[PersistedPublicEvent],
    ) -> ProjectView:
        offered = (
            session.validation_queue.offered if session.validation_queue is not None else []
        )
        return ProjectView(
            project_id=project.project_id,
            title=project.title,
            domain=project.domain,
            version=project.version,
            phase=session.phase,
            is_demo=project.is_demo,
            allowed_commands=list(allowed_commands(session)),
            last_event_sequence=last_event_sequence,
            active_run=(
                ActiveRunView(
                    run_id=active_run.run_id,
                    agent_name=active_run.agent_name,
                    status=active_run.status,
                    public_message=active_run.public_message,
                )
                if active_run is not None
                else None
            ),
            validation_candidates=[item.model_copy(deep=True) for item in offered],
            visible_evidence=_visible_evidence(session, literature),
            stage_progress=_stage_progress(session, active_run),
            recent_activity=_recent_activity(events),
            plan_candidates=_plan_candidates(session),
            current_task=_current_task_view(session.current_task),
            writing_guidance=(
                session.writing_guidance.model_copy(deep=True)
                if session.writing_guidance is not None
                else None
            ),
            revision_reason=_revision_reason(session),
            working_turns=_working_turns(events),
            pending_clarification=(
                session.pending_working_clarification.model_copy(deep=True)
                if session.pending_working_clarification is not None
                else None
            ),
        )


_RUN_HEADLINES = {
    "idea_review": "正在检索文献并审查研究想法",
    "plan_loop": "正在生成研究方案",
    "key_insight_check": "正在校验点睛之笔",
    "working_qa": "正在回答实验问题",
    "complete": "正在整理完成建议",
}

_PHASE_HEADLINES = {
    SessionPhase.AWAITING_IDEA: "等待提交研究想法",
    SessionPhase.AWAITING_IDEA_REFINEMENT: "等待补充研究边界",
    SessionPhase.PLANNING: "Idea 已通过，等待生成研究方案",
    SessionPhase.CHECKING_KEY_INSIGHT: "研究方案已生成，等待校验点睛之笔",
    SessionPhase.AWAITING_PLAN_DECISION: "点睛之笔已通过，等待确认方案",
    SessionPhase.CHECK_LOOP_EXHAUSTED: "校验轮次已用尽，等待你的决定",
    SessionPhase.AWAITING_WORKING_CONTEXT: "准备实验上下文",
    SessionPhase.WORKING: "实验问答进行中",
    SessionPhase.AWAITING_RESULT_RECORD: "等待记录实验结果",
    SessionPhase.COMPLETING: "等待整理完成建议",
    SessionPhase.AWAITING_VALIDATION_SELECTION: "等待选择补充验证",
    SessionPhase.AWAITING_PLAN_REVISION_DECISION: "等待确认修订方向",
    SessionPhase.COMPLETED: "研究流程已完成",
    SessionPhase.REJECTED: "当前想法未通过准入",
}


def _plan_candidates(session: ResearchSession) -> list[PlanCandidateView]:
    views: list[PlanCandidateView] = []
    for item in session.plan_candidates:
        plan = item.plan
        views.append(
            PlanCandidateView(
                candidate_id=item.candidate_id,
                disposition=item.disposition,
                focus_hint=item.focus_hint,
                check_round=item.check_round,
                research_question=plan.research_question if plan is not None else None,
                key_insight_title=plan.key_insight.title if plan is not None else None,
                key_insight_content=plan.key_insight.content if plan is not None else None,
            )
        )
    return views


def _current_task_view(
    task: ExperimentTaskContext | None,
) -> CurrentTaskView | None:
    if task is None:
        return None
    return CurrentTaskView(
        task_id=task.task_id,
        task_kind=task.task_kind,
        origin=task.origin,
        status=task.status,
        current_experiment=task.experiment_info.current_experiment,
        expected_result=task.experiment_info.expected_result,
        validation_task=(
            task.validation_task.model_copy(deep=True)
            if task.validation_task is not None
            else None
        ),
    )


def _revision_reason(session: ResearchSession) -> str | None:
    if session.pending_plan_issue_reason is not None:
        return session.pending_plan_issue_reason
    output = session.latest_complete_output
    if output is not None:
        return output.revision_reason
    return None


def _working_turns(events: list[PersistedPublicEvent]) -> list[WorkingTurnView]:
    items: list[WorkingTurnView] = []
    for event in events:
        if event.event_type != "working_turn_completed":
            continue
        action = event.payload.get("action")
        reply = event.payload.get("reply")
        if not isinstance(action, str) or not action.strip():
            continue
        if not isinstance(reply, str) or not reply.strip():
            continue
        reason = event.payload.get("reason")
        question = event.payload.get("question")
        items.append(
            WorkingTurnView(
                question=question if isinstance(question, str) else "",
                action=action,
                reply=reply,
                reason=reason if isinstance(reason, str) else "",
                occurred_at=event.occurred_at.isoformat()
                if event.occurred_at is not None
                else None,
            )
        )
    return items


def _evidence_key(*, title: str, url: str | None, record_id: str | None = None) -> str:
    return url or record_id or title


def _adopted_evidence_keys(session: ResearchSession) -> set[str]:
    keys: set[str] = set()
    review = session.idea_review
    if review is not None:
        for evidence in review.evidence:
            keys.add(_evidence_key(title=evidence.title, url=evidence.url))
            if evidence.source_id:
                keys.add(evidence.source_id)
    check = session.latest_check
    if check is not None:
        for evidence in check.assessment.evidence:
            keys.add(_evidence_key(title=evidence.title, url=evidence.url))
            if evidence.source_id:
                keys.add(evidence.source_id)
    for candidate in session.plan_candidates:
        for round_item in candidate.check_history:
            for evidence in round_item.output.assessment.evidence:
                keys.add(_evidence_key(title=evidence.title, url=evidence.url))
                if evidence.source_id:
                    keys.add(evidence.source_id)
    return keys


def _visible_evidence(
    session: ResearchSession, literature: list[LiteratureRecord]
) -> list[VisibleEvidenceItem]:
    adopted = _adopted_evidence_keys(session)
    items: list[VisibleEvidenceItem] = []
    seen: set[str] = set()

    def append_item(
        *,
        title: str,
        source_type: str,
        url: str | None,
        summary: str | None = None,
        support: str | None = None,
        record_id: str | None = None,
    ) -> None:
        key = _evidence_key(title=title, url=url, record_id=record_id)
        if key in seen:
            return
        seen.add(key)
        selected = key in adopted or title in adopted or (record_id in adopted if record_id else False)
        items.append(
            VisibleEvidenceItem(
                title=title,
                source_type=source_type,
                url=url,
                summary=summary,
                support=support,
                selected=selected,
            )
        )

    for record in literature:
        append_item(
            title=record.title,
            source_type=record.source_type,
            url=record.url,
            summary=record.summary,
            record_id=record.record_id,
        )
    review = session.idea_review
    if review is not None:
        for record in review.literature_searches:
            append_item(
                title=record.title,
                source_type=record.source_type,
                url=record.url,
                summary=record.summary,
                record_id=record.record_id,
            )
        for evidence in review.evidence:
            append_item(
                title=evidence.title,
                source_type=evidence.source_type,
                url=evidence.url,
                support=evidence.support,
                record_id=evidence.source_id,
            )
    check = session.latest_check
    if check is not None:
        for evidence in check.assessment.evidence:
            append_item(
                title=evidence.title,
                source_type=evidence.source_type,
                url=evidence.url,
                support=evidence.support,
                record_id=evidence.source_id,
            )
    return items


def _stage_progress(
    session: ResearchSession, active_run: AgentRun | None
) -> StageProgress:
    review = session.idea_review
    plan = session.active_plan
    candidates = session.plan_candidates
    check_round = max(
        [session.check_round, *(item.check_round for item in candidates)],
        default=0,
    )
    last_check = session.latest_check
    if last_check is None and candidates:
        history = candidates[0].check_history
        if history:
            last_check = history[-1].output
    running = (
        active_run is not None and active_run.status in {"queued", "running"}
    )
    if running and active_run is not None:
        headline = _RUN_HEADLINES.get(active_run.agent_name, "正在运行")
        if active_run.agent_name == "key_insight_check":
            headline = f"{headline}（第 {check_round + 1}/{MAX_CHECK_ROUNDS} 轮）"
        detail = active_run.public_message
    else:
        headline = _PHASE_HEADLINES[session.phase]
        detail = None
        if review is not None and session.phase in {
            SessionPhase.PLANNING,
            SessionPhase.AWAITING_IDEA_REFINEMENT,
            SessionPhase.REJECTED,
        }:
            detail = review.reason
        elif last_check is not None and session.phase in {
            SessionPhase.CHECKING_KEY_INSIGHT,
            SessionPhase.AWAITING_PLAN_DECISION,
            SessionPhase.CHECK_LOOP_EXHAUSTED,
            SessionPhase.PLANNING,
        }:
            detail = last_check.decision_reason
    return StageProgress(
        headline=headline,
        detail=detail,
        check_round=check_round,
        max_check_rounds=MAX_CHECK_ROUNDS,
        candidate_count=len(candidates),
        idea_type=review.idea_type if review is not None else None,
        idea_action=review.action if review is not None else None,
        idea_reason=review.reason if review is not None else None,
        normalized_idea=review.normalized_idea if review is not None else None,
        plan_question=plan.research_question if plan is not None else None,
        key_insight_title=plan.key_insight.title if plan is not None else None,
        last_check_score=last_check.final_score if last_check is not None else None,
        last_check_passed=last_check.check_decision if last_check is not None else None,
    )


def _recent_activity(
    events: list[PersistedPublicEvent],
) -> list[PublicActivityItem]:
    from research_mentor.application.event_stream import _event_summary, _project

    items: list[PublicActivityItem] = []
    for event in events:
        projected = _project(event)
        if projected is None:
            continue
        public_type, payload = projected
        items.append(
            PublicActivityItem(
                sequence=event.sequence,
                type=public_type,
                summary=_event_summary(public_type, payload),
            )
        )
    return items[-12:]

