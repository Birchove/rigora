"""Production command and durable-run handlers."""

import logging
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from research_mentor.application.commands import (
    AgentCommandReceipt,
    ArchiveProjectCommand,
    CommandBase,
    CommandResult,
    ContinueImperfectPlanDecision,
    DecidePlanCommand,
    DecidePlanRevisionCommand,
    DeterministicCommandResult,
    RecordMainResultCommand,
    RecordValidationResultCommand,
    ResumeWorkingCommand,
    FinishWorkingCommand,
    SelectValidationsCommand,
)
from research_mentor.adapters.embeddings.lexical import LexicalRanker
from research_mentor.application.context_service import (
    WorkingContextBuilder,
    WorkingContextSource,
)
from research_mentor.application.handlers import CancelRunHandler, RestartResearchHandler
from research_mentor.application.orchestration import apply_orchestrator
from research_mentor.config import Settings
from research_mentor.domain.evidence import EvidenceRef
from research_mentor.domain.jobs import AgentRun
from research_mentor.domain.projects import ResearchProject
from research_mentor.domain.research import InitialInput
from research_mentor.errors import InvariantViolationError, LiteratureSearchUnavailable
from research_mentor.harness.orchestrator import ResearchMentorOrchestrator
from research_mentor.harness.phase import SessionPhase
from research_mentor.harness.retrieval_context import (
    IdeaReviewRetrievalPipeline,
    IdentityLiteratureRanker,
    LiteratureBatchRetriever,
)
from research_mentor.harness.state import ResearchSession
from research_mentor.harness.task_factory import TaskFactory
from research_mentor.hyperparameters import OPENALEX_DEFAULT_LIMIT
from research_mentor.ports.model import StructuredModelPort


logger = logging.getLogger("research_mentor.runs")


_AGENT_BY_COMMAND = {
    "submit_idea": "idea_review",
    "submit_refinement": "idea_review",
    "run_plan": "plan_loop",
    "run_check": "key_insight_check",
    "send_working_message": "working_qa",
    "run_complete": "complete",
}


class EnqueueAgentHandler:
    def __init__(
        self,
        agent_name: str,
        *,
        new_id: Callable[[], str] | None = None,
    ) -> None:
        self._agent_name = agent_name
        self._new_id = new_id or (lambda: str(uuid4()))

    async def __call__(
        self,
        command: CommandBase,
        uow: Any,
        project: ResearchProject,
        session: ResearchSession,
    ) -> CommandResult:
        del session
        run_id = self._new_id()
        await uow.runs.add(
            AgentRun(
                run_id=run_id,
                project_id=project.project_id,
                command_id=command.command_id,
                agent_name=self._agent_name,  # type: ignore[arg-type]
                status="queued",
                attempt=0,
                input_snapshot=command.model_dump(mode="json"),
            )
        )
        return AgentCommandReceipt(
            project_id=project.project_id,
            command_id=command.command_id,
            run_id=run_id,
        )


class _OrchestratingHandler:
    def __init__(self, *, model: StructuredModelPort, settings: Settings) -> None:
        self._model = model
        self._settings = settings

    async def _apply(
        self,
        command: CommandBase,
        uow: Any,
        project: ResearchProject,
        session: ResearchSession,
        mutate: Callable[[ResearchMentorOrchestrator, str], None],
    ) -> DeterministicCommandResult:
        updated = await apply_orchestrator(
            uow,
            project_id=project.project_id,
            session=session,
            model=self._model,
            settings=self._settings,
            mutate=mutate,
        )
        return DeterministicCommandResult(
            project_id=project.project_id,
            command_id=command.command_id,
            session_id=updated.session_id,
            version=project.version,
            phase=updated.phase,
        )


class DecidePlanHandler(_OrchestratingHandler):
    async def __call__(
        self,
        command: CommandBase,
        uow: Any,
        project: ResearchProject,
        session: ResearchSession,
    ) -> CommandResult:
        if not isinstance(command, DecidePlanCommand):
            raise TypeError("DecidePlanHandler requires decide_plan")

        def mutate(orchestrator: ResearchMentorOrchestrator, session_id: str) -> None:
            if isinstance(command.decision, ContinueImperfectPlanDecision):
                current = orchestrator._repository.get(session_id)
                candidate_id = command.candidate_id
                if candidate_id is None:
                    exhausted = [
                        item
                        for item in current.plan_candidates
                        if item.disposition == "exhausted"
                    ]
                    if len(exhausted) != 1:
                        raise InvariantViolationError(
                            "continue_imperfect requires candidate_id"
                        )
                    candidate_id = exhausted[0].candidate_id
                orchestrator.continue_imperfect_plan(
                    session_id,
                    candidate_id,
                    user_reason=command.decision.user_reason,
                )
                return
            orchestrator.decide_plan(
                session_id,
                command.decision,
                candidate_id=command.candidate_id,
            )
            current = orchestrator._repository.get(session_id)
            if (
                current.phase is SessionPhase.AWAITING_WORKING_CONTEXT
                and current.active_plan is not None
            ):
                orchestrator.start_working(
                    session_id,
                    TaskFactory.from_plan(current.active_plan),
                )

        return await self._apply(command, uow, project, session, mutate)


class ResumeWorkingHandler(_OrchestratingHandler):
    async def __call__(
        self,
        command: CommandBase,
        uow: Any,
        project: ResearchProject,
        session: ResearchSession,
    ) -> CommandResult:
        if not isinstance(command, ResumeWorkingCommand):
            raise TypeError("ResumeWorkingHandler requires resume_working")
        return await self._apply(
            command,
            uow,
            project,
            session,
            lambda orchestrator, session_id: orchestrator.resume_working(session_id),
        )


class FinishWorkingHandler(_OrchestratingHandler):
    async def __call__(
        self,
        command: CommandBase,
        uow: Any,
        project: ResearchProject,
        session: ResearchSession,
    ) -> CommandResult:
        if not isinstance(command, FinishWorkingCommand):
            raise TypeError("FinishWorkingHandler requires finish_working")
        return await self._apply(
            command,
            uow,
            project,
            session,
            lambda orchestrator, session_id: orchestrator.finish_working(session_id),
        )


class RecordMainResultHandler(_OrchestratingHandler):
    async def __call__(
        self,
        command: CommandBase,
        uow: Any,
        project: ResearchProject,
        session: ResearchSession,
    ) -> CommandResult:
        if not isinstance(command, RecordMainResultCommand):
            raise TypeError("RecordMainResultHandler requires record_main_result")
        return await self._apply(
            command,
            uow,
            project,
            session,
            lambda orchestrator, session_id: orchestrator.record_main_result(
                session_id, command.result
            ),
        )


class RecordValidationResultHandler(_OrchestratingHandler):
    async def __call__(
        self,
        command: CommandBase,
        uow: Any,
        project: ResearchProject,
        session: ResearchSession,
    ) -> CommandResult:
        if not isinstance(command, RecordValidationResultCommand):
            raise TypeError("RecordValidationResultHandler requires record_validation_result")
        return await self._apply(
            command,
            uow,
            project,
            session,
            lambda orchestrator, session_id: orchestrator.record_validation_result(
                session_id, command.result
            ),
        )


class SelectValidationsHandler(_OrchestratingHandler):
    async def __call__(
        self,
        command: CommandBase,
        uow: Any,
        project: ResearchProject,
        session: ResearchSession,
    ) -> CommandResult:
        if not isinstance(command, SelectValidationsCommand):
            raise TypeError("SelectValidationsHandler requires select_validations")
        return await self._apply(
            command,
            uow,
            project,
            session,
            lambda orchestrator, session_id: orchestrator.select_validations(
                session_id, command.selection
            ),
        )


class DecidePlanRevisionHandler(_OrchestratingHandler):
    async def __call__(
        self,
        command: CommandBase,
        uow: Any,
        project: ResearchProject,
        session: ResearchSession,
    ) -> CommandResult:
        if not isinstance(command, DecidePlanRevisionCommand):
            raise TypeError("DecidePlanRevisionHandler requires decide_plan_revision")
        return await self._apply(
            command,
            uow,
            project,
            session,
            lambda orchestrator, session_id: orchestrator.decide_plan_revision(
                session_id,
                command.decision,
                user_reason=command.user_reason,
            ),
        )


class ArchiveProjectHandler:
    async def __call__(
        self,
        command: CommandBase,
        uow: Any,
        project: ResearchProject,
        session: ResearchSession,
    ) -> CommandResult:
        if not isinstance(command, ArchiveProjectCommand):
            raise TypeError("ArchiveProjectHandler requires archive_project")
        del uow
        return DeterministicCommandResult(
            project_id=project.project_id,
            command_id=command.command_id,
            session_id=session.session_id,
            version=project.version,
            phase=session.phase,
            payload={"archived": True},
        )


class AgentRunHandlers:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        *,
        model: StructuredModelPort,
        settings: Settings,
        retriever: LiteratureBatchRetriever | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._model = model
        self._settings = settings
        self._pipeline = None
        if retriever is not None:
            self._pipeline = IdeaReviewRetrievalPipeline(
                model=model,
                retriever=retriever,
                ranker=IdentityLiteratureRanker(),
                model_profile=settings.agent_models().get("idea_review", "default"),
                openalex_limit=OPENALEX_DEFAULT_LIMIT,
            )

    def mapping(self) -> dict[str, Any]:
        return {
            "idea_review": self.idea_review,
            "plan_loop": self.plan_loop,
            "key_insight_check": self.key_insight_check,
            "working_qa": self.working_qa,
            "complete": self.complete,
        }

    async def idea_review(
        self, run: AgentRun, snapshot: dict[str, Any], repair_errors: list[dict[str, Any]] | None
    ) -> None:
        del repair_errors
        idea = await self._idea_for_run(run, snapshot)
        prepared = None
        records: list[Any] = []
        if self._pipeline is not None:
            try:
                transaction = await self._pipeline.review(
                    project_id=run.project_id, initial_input=idea
                )
                prepared = transaction.review
                records = list(transaction.literature_records)
            except (LiteratureSearchUnavailable, Exception):
                logger.exception(
                    "idea review retrieval failed project=%s run=%s",
                    run.project_id,
                    run.run_id,
                )
        await self._run(
            run,
            lambda orchestrator, session_id: orchestrator.review_idea(
                session_id, idea, prepared=prepared
            ),
        )
        await self._persist_literature(run.project_id, records)

    async def plan_loop(
        self, run: AgentRun, snapshot: dict[str, Any], repair_errors: list[dict[str, Any]] | None
    ) -> None:
        del repair_errors
        mode = snapshot.get("mode") or "low"
        await self._run(
            run,
            lambda orchestrator, session_id: orchestrator.run_plan(session_id, mode=mode),
        )

    async def key_insight_check(
        self, run: AgentRun, snapshot: dict[str, Any], repair_errors: list[dict[str, Any]] | None
    ) -> None:
        del repair_errors
        candidate_id = snapshot.get("candidate_id")

        def mutate(orchestrator: ResearchMentorOrchestrator, session_id: str) -> None:
            current = orchestrator._repository.get(session_id)
            if current.plan_candidates:
                orchestrator.run_check(session_id, candidate_id=candidate_id)
            else:
                orchestrator.run_key_insight_check(session_id)

        await self._run(run, mutate)

    async def working_qa(
        self, run: AgentRun, snapshot: dict[str, Any], repair_errors: list[dict[str, Any]] | None
    ) -> None:
        del repair_errors
        question = str(snapshot.get("question") or "")
        context = await self._build_working_context(run.project_id, question)
        await self._run(
            run,
            lambda orchestrator, session_id: orchestrator.run_working_qa(
                session_id, question, working_context=context
            ),
        )

    async def complete(
        self, run: AgentRun, snapshot: dict[str, Any], repair_errors: list[dict[str, Any]] | None
    ) -> None:
        del repair_errors
        completion_status = bool(snapshot.get("completion_status", True))
        await self._run(
            run,
            lambda orchestrator, session_id: orchestrator.run_complete(
                session_id, completion_status
            ),
        )

    async def _idea_for_run(self, run: AgentRun, snapshot: dict[str, Any]) -> InitialInput:
        if "idea" in snapshot:
            return InitialInput.model_validate(snapshot["idea"])
        async with self._uow_factory() as uow:
            project = await uow.projects.get(run.project_id)
            if project is None:
                raise InvariantViolationError(f"Project not found: {run.project_id}")
            session = await uow.sessions.get(project.session_id)
            if session is None or session.initial_input is None:
                raise InvariantViolationError("idea_review requires initial_input")
            return session.initial_input.model_copy(
                update={"original_idea": str(snapshot.get("refinement") or "")}
            )

    async def _build_working_context(self, project_id: str, question: str):
        async with self._uow_factory() as uow:
            project = await uow.projects.get(project_id)
            if project is None:
                return None
            session = await uow.sessions.get(project.session_id)
            if (
                session is None
                or session.research_context is None
                or session.current_task is None
            ):
                return None
            chunks = []
            list_chunks = getattr(uow.documents, "list_chunks_for_project", None)
            if callable(list_chunks):
                chunks = await list_chunks(project_id)
            records = await uow.literature.list_for_project(project_id)
        observations = list(session.current_task.experiment_info.observations)
        actual = session.current_task.experiment_info.actual_result
        facts = [item for item in observations if item.strip()]
        if actual and actual.strip():
            facts.append(actual)
        evidence_refs = [
            EvidenceRef(
                source_id=record.record_id,
                title=record.title,
                authors=list(record.authors),
                year=record.year,
                source_type=record.source_type,
                url=record.url,
                doi=record.doi,
                support=record.relevance or record.summary,
            )
            for record in records
        ]
        builder = WorkingContextBuilder(self._settings, LexicalRanker())
        return await builder.build(
            WorkingContextSource(
                research_context=session.research_context,
                current_task=session.current_task,
                document_chunks=chunks,
                evidence_refs=evidence_refs,
                facts=facts,
                current_stage=session.phase.value,
            ),
            question,
        )

    async def _persist_literature(
        self, project_id: str, records: list[Any]
    ) -> None:
        if not records:
            return
        async with self._uow_factory() as uow:
            for record in records:
                try:
                    await uow.literature.add_for_project(
                        project_id, record, selected=False
                    )
                except ValueError:
                    continue

    async def _run(
        self,
        run: AgentRun,
        mutate: Callable[[ResearchMentorOrchestrator, str], None],
    ) -> None:
        async with self._uow_factory() as uow:
            project = await uow.projects.get(run.project_id)
            if project is None:
                raise InvariantViolationError(f"Project not found: {run.project_id}")
            session = await uow.sessions.get(project.session_id)
            if session is None:
                raise InvariantViolationError(f"Session not found: {project.session_id}")
            await apply_orchestrator(
                uow,
                project_id=project.project_id,
                session=session,
                model=self._model,
                settings=self._settings,
                mutate=mutate,
            )

    @staticmethod
    def _review_idea(
        orchestrator: ResearchMentorOrchestrator,
        session_id: str,
        snapshot: dict[str, Any],
    ) -> None:
        if "idea" in snapshot:
            idea = InitialInput.model_validate(snapshot["idea"])
        else:
            current = orchestrator._repository.get(session_id)
            if current.initial_input is None:
                raise InvariantViolationError("idea_review requires initial_input")
            idea = current.initial_input.model_copy(
                update={"original_idea": str(snapshot.get("refinement") or "")}
            )
        orchestrator.review_idea(session_id, idea)


def build_command_handlers(
    *,
    model: StructuredModelPort,
    settings: Settings,
) -> dict[str, Any]:
    return {
        command_type: EnqueueAgentHandler(agent_name)
        for command_type, agent_name in _AGENT_BY_COMMAND.items()
    } | {
        "decide_plan": DecidePlanHandler(model=model, settings=settings),
        "resume_working": ResumeWorkingHandler(model=model, settings=settings),
        "finish_working": FinishWorkingHandler(model=model, settings=settings),
        "record_main_result": RecordMainResultHandler(model=model, settings=settings),
        "record_validation_result": RecordValidationResultHandler(
            model=model, settings=settings
        ),
        "select_validations": SelectValidationsHandler(model=model, settings=settings),
        "decide_plan_revision": DecidePlanRevisionHandler(model=model, settings=settings),
        "cancel_run": CancelRunHandler(),
        "restart_research": RestartResearchHandler(),
        "archive_project": ArchiveProjectHandler(),
    }


def build_run_handlers(
    uow_factory: Callable[[], Any],
    *,
    model: StructuredModelPort,
    settings: Settings,
    retriever: LiteratureBatchRetriever | None = None,
) -> dict[str, Any]:
    return AgentRunHandlers(
        uow_factory, model=model, settings=settings, retriever=retriever
    ).mapping()
