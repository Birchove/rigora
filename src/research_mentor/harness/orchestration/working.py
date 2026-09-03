"""Working QA, result recording, and working-phase transitions."""

from research_mentor.agents.working_qa.contracts import (
    WorkingContext,
    WorkingQAInput,
    WorkingQAOutput,
    WorkingQASysInput,
)
from research_mentor.domain.experiments import ExperimentTaskContext, MainExperimentResult, ValidationResult
from research_mentor.domain.research import ResearchContext, ResearchPlan
from research_mentor.errors import InvariantViolationError
from research_mentor.harness.orchestration.base import OrchestratorBase
from research_mentor.harness.routing import route_working_output
from research_mentor.harness.state import ResearchSession, SessionEventType, SessionPhase
from research_mentor.harness.session_slices import PendingWorkingClarification


class WorkingOrchestrator(OrchestratorBase):
    def start_working(
        self,
        session_id: str,
        task_context: ExperimentTaskContext,
        plan: ResearchPlan | None = None,
    ) -> ResearchSession:
        session = self._load_for_phase(
            session_id, {SessionPhase.AWAITING_WORKING_CONTEXT}
        )
        if session.initial_input is None or session.idea_review is None:
            raise InvariantViolationError("working requires initial_input and idea_review")
        if task_context.status != "in_progress":
            raise InvariantViolationError("working task must be in_progress")
        current_experiment = task_context.experiment_info.current_experiment
        if current_experiment is None or not current_experiment.strip():
            raise InvariantViolationError("working task requires current_experiment")
        if session.active_plan is None:
            payload = task_context.model_dump(mode="json")
            if plan is not None:
                session.active_plan = plan.model_copy(deep=True)
                session.research_context = ResearchContext(
                    normalized_idea=session.idea_review.normalized_idea,
                    research_question=plan.research_question,
                    plan=plan.model_copy(deep=True),
                )
                payload["active_plan"] = plan.model_dump(mode="json")
            elif session.research_context is None or session.research_context.forward_context is None:
                raise InvariantViolationError("planless working requires forward research context")
        else:
            if plan is not None:
                raise InvariantViolationError("accepted working plan cannot be replaced")
            session.research_context = ResearchContext(
                normalized_idea=session.idea_review.normalized_idea,
                research_question=session.active_plan.research_question,
                plan=session.active_plan.model_copy(deep=True),
            )
            payload = task_context.model_dump(mode="json")

        phase_before = session.phase
        session.current_task = task_context.model_copy(deep=True)
        session.phase = SessionPhase.WORKING
        event = self._event(
            session_id,
            SessionEventType.WORKING_STARTED,
            phase_before,
            session.phase,
            payload,
        )
        self._commit(session, event)
        return session.model_copy(deep=True)

    def run_working_qa(
        self,
        session_id: str,
        question: str,
        *,
        working_context: WorkingContext | None = None,
    ) -> WorkingQAOutput:
        session = self._load_for_phase(session_id, {SessionPhase.WORKING})
        if (
            session.initial_input is None
            or session.idea_review is None
            or session.research_context is None
            or session.current_task is None
        ):
            raise InvariantViolationError(
                "working QA requires initial_input, idea_review, research_context, and current_task"
            )

        phase_before = session.phase
        context = working_context
        output = self._working_qa_runner.run_sync(
            WorkingQAInput(
                idea=session.initial_input.model_copy(deep=True),
                question=question,
                sys_input=WorkingQASysInput(current_date=self._current_date()),
                research_context=session.research_context.model_copy(deep=True),
                task_context=session.current_task.model_copy(deep=True),
                conversation_turns=[] if context is None else list(context.recent_turns),
                compact_context=None if context is None else context.compact_context,
                evidence_refs=[] if context is None else list(context.evidence_refs),
                retrieval_diagnostics=(
                    [] if context is None else list(context.retrieval_diagnostics)
                ),
                rank_status="ok" if context is None else context.rank_status,
                top_relevance=None if context is None else context.top_relevance,
                decline_as_unrelated=(
                    False if context is None else context.decline_as_unrelated
                ),
            ),
            model_profile=self._agent_model("working_qa"),
        )
        if output.updated_experiment_info is not None:
            session.current_task = session.current_task.model_copy(
                update={
                    "experiment_info": output.updated_experiment_info.model_copy(deep=True)
                }
            )
        if output.action == "report_plan_issue" and session.current_task.task_kind != "main":
            raise InvariantViolationError("only a main task may report a plan issue")
        if output.action == "report_plan_issue":
            session.pending_plan_issue_reason = output.reason
        if output.action == "clarify":
            prior = session.pending_working_clarification
            session.pending_working_clarification = PendingWorkingClarification(
                original_question=(
                    prior.original_question if prior is not None else question
                ),
                clarify_reply=output.reply,
                clarify_reason=output.reason,
            )
        else:
            session.pending_working_clarification = None
        phase_after = route_working_output(output)
        session.phase = phase_after
        event = self._event(
            session_id,
            SessionEventType.WORKING_TURN_COMPLETED,
            phase_before,
            phase_after,
            {**output.model_dump(mode="json"), "question": question},
        )
        self._commit(session, event)
        return output.model_copy(deep=True)

    def resume_working(self, session_id: str) -> ResearchSession:
        session = self._load_for_phase(session_id, {SessionPhase.AWAITING_RESULT_RECORD})
        if session.current_task is None or session.current_task.status != "in_progress":
            raise InvariantViolationError("resume requires an in-progress completion proposal")
        phase_before = session.phase
        session.phase = SessionPhase.WORKING
        event = self._event(
            session_id,
            SessionEventType.WORKING_RESUMED,
            phase_before,
            session.phase,
            {"task_id": session.current_task.task_id},
        )
        self._commit(session, event)
        return session.model_copy(deep=True)

    def finish_working(self, session_id: str) -> ResearchSession:
        session = self._load_for_phase(session_id, {SessionPhase.WORKING})
        if session.current_task is None or session.current_task.status != "in_progress":
            raise InvariantViolationError("finish_working requires an in-progress current task")
        phase_before = session.phase
        session.pending_working_clarification = None
        session.phase = SessionPhase.AWAITING_RESULT_RECORD
        event = self._event(
            session_id,
            SessionEventType.WORKING_FINISHED,
            phase_before,
            session.phase,
            {"task_id": session.current_task.task_id},
        )
        self._commit(session, event)
        return session.model_copy(deep=True)

    def record_main_result(
        self,
        session_id: str,
        result: MainExperimentResult,
    ) -> ResearchSession:
        session = self._load_for_phase(
            session_id, {SessionPhase.AWAITING_RESULT_RECORD}
        )
        if session.current_task is None or session.current_task.task_kind != "main":
            raise InvariantViolationError("main result requires a current main task")
        if session.current_task.status != "in_progress":
            raise InvariantViolationError("result recording requires an in-progress proposal")

        phase_before = session.phase
        session.main_experiment = result.model_copy(deep=True)
        session.current_task = session.current_task.model_copy(update={"status": "completed"})
        session.phase = SessionPhase.COMPLETING
        event = self._event(
            session_id,
            SessionEventType.RESULT_RECORDED,
            phase_before,
            session.phase,
            result.model_dump(mode="json"),
        )
        self._commit(session, event)
        return session.model_copy(deep=True)

    def record_validation_result(
        self,
        session_id: str,
        result: ValidationResult,
    ) -> ResearchSession:
        session = self._load_for_phase(
            session_id, {SessionPhase.AWAITING_RESULT_RECORD}
        )
        if session.current_task is None or session.current_task.task_kind != "validation":
            raise InvariantViolationError("validation result requires a current validation task")
        if session.current_task.status != "in_progress":
            raise InvariantViolationError("result recording requires an in-progress proposal")
        if session.main_experiment is None:
            raise InvariantViolationError("validation result requires a main experiment")
        if session.current_task.validation_task != result.task:
            raise InvariantViolationError("validation result must match the current task")

        phase_before = session.phase
        session.completed_validations.append(result.model_copy(deep=True))
        session.current_task = session.current_task.model_copy(update={"status": "completed"})
        if session.validation_queue is not None:
            for item in session.validation_queue.selected:
                if item.status == "active" and item.candidate.task == result.task:
                    item.status = "completed"
        session.phase = SessionPhase.COMPLETING
        event = self._event(
            session_id,
            SessionEventType.RESULT_RECORDED,
            phase_before,
            session.phase,
            result.model_dump(mode="json"),
        )
        self._commit(session, event)
        return session.model_copy(deep=True)
