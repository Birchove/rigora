"""Complete guidance, validation selection, and plan-revision decisions."""

from research_mentor.agents.complete.contracts import (
    CompleteAgentInput,
    CompleteAgentOutput,
    CompleteAgentSysInput,
)
from research_mentor.agents.plan_loop.contracts import PlanRevisionContext
from research_mentor.domain.completion import ValidationSelection
from research_mentor.domain.research import UserPlanFeedback
from research_mentor.errors import InvariantViolationError
from research_mentor.harness.orchestration.base import OrchestratorBase
from research_mentor.harness.routing import route_complete
from research_mentor.harness.state import PlanRevisionRecord, ResearchSession, SessionEventType, SessionPhase
from research_mentor.harness.task_factory import TaskFactory
from research_mentor.harness.validation import ValidationQueue, validation_task_identity


class CompletionOrchestrator(OrchestratorBase):
    def run_complete(
        self,
        session_id: str,
        completion_status: bool,
    ) -> CompleteAgentOutput:
        session = self._load_for_phase(session_id, {SessionPhase.COMPLETING})
        if (
            session.initial_input is None
            or session.idea_review is None
            or session.research_context is None
            or session.main_experiment is None
        ):
            raise InvariantViolationError(
                "completion requires initial_input, idea_review, research_context, and main_experiment"
            )
        if session.research_context.plan is not None and session.active_plan is None:
            raise InvariantViolationError("planned completion requires active_plan")

        pending = None
        if session.validation_queue is not None:
            pending = next(
                (item for item in session.validation_queue.selected if item.status == "pending"),
                None,
            )

        phase_before = session.phase
        output = self._complete_runner.run_sync(
            CompleteAgentInput(
                idea=session.initial_input.model_copy(deep=True),
                normalized_idea=session.idea_review.normalized_idea,
                sys_input=CompleteAgentSysInput(
                    current_date=self._current_date(), completion_status=completion_status
                ),
                research_context=session.research_context.model_copy(deep=True),
                plan=session.active_plan.model_copy(deep=True) if session.active_plan else None,
                main_experiment=session.main_experiment.model_copy(deep=True),
                completed_validations=[
                    result.model_copy(deep=True)
                    for result in session.completed_validations
                ],
            ),
            model_profile=self._agent_model("complete"),
        )
        phase_after = route_complete(output).next_phase
        session.latest_complete_output = output.model_copy(deep=True)
        if output.mode == "validation":
            handled_ids = set()
            handled_task_identities = {
                validation_task_identity(item.task)
                for item in session.completed_validations
            }
            previous_queue = session.validation_queue
            existing_candidates = []
            if previous_queue is not None:
                handled = [
                    *previous_queue.selected,
                    *previous_queue.skipped,
                ]
                handled_ids = {
                    item.candidate.candidate_id
                    for item in handled
                }
                handled_task_identities.update({
                    validation_task_identity(item.candidate.task)
                    for item in handled
                })
                for item in previous_queue.offered:
                    identity = validation_task_identity(item.task)
                    if (
                        item.candidate_id not in handled_ids
                        and identity not in handled_task_identities
                    ):
                        existing_candidates.append(item.model_copy(deep=True))
                        handled_task_identities.add(identity)
            merged_candidates = list(existing_candidates)
            merged_ids = {item.candidate_id for item in merged_candidates}
            for item in output.validation_candidates:
                identity = validation_task_identity(item.task)
                if (
                    item.candidate_id not in handled_ids
                    and item.candidate_id not in merged_ids
                    and identity not in handled_task_identities
                ):
                    merged_candidates.append(item.model_copy(deep=True))
                    merged_ids.add(item.candidate_id)
                    handled_task_identities.add(identity)
            next_queue = ValidationQueue.from_candidates(
                merged_candidates,
            )
            if previous_queue is not None:
                next_queue.selected = [
                    item.model_copy(deep=True) for item in previous_queue.selected
                ]
                next_queue.skipped = [
                    item.model_copy(deep=True) for item in previous_queue.skipped
                ]
            session.validation_queue = next_queue
            if pending is not None:
                pending = next(
                    item
                    for item in next_queue.selected
                    if item.candidate.candidate_id == pending.candidate.candidate_id
                )
        if output.mode != "plan_revision" and pending is not None:
            self._activate_validation(session, pending)
            phase_after = session.phase
        elif output.mode == "writing":
            session.writing_guidance = output.writing_guidance.model_copy(deep=True)
        session.phase = phase_after
        payload = output.model_dump(mode="json")
        payload["completion_status"] = completion_status
        event = self._event(
            session_id,
            SessionEventType.COMPLETE_GUIDANCE_GENERATED,
            phase_before,
            phase_after,
            payload,
        )
        self._commit(session, event)
        return output.model_copy(deep=True)

    def select_validations(
        self, session_id: str, selection: ValidationSelection
    ) -> ResearchSession:
        session = self._load_for_phase(
            session_id, {SessionPhase.AWAITING_VALIDATION_SELECTION}
        )
        if session.validation_queue is None or session.current_task is None:
            raise InvariantViolationError("validation selection requires a queue and main task")
        phase_before = session.phase
        queue = session.validation_queue.apply(selection)
        session.validation_queue = queue
        active = next((item for item in queue.selected if item.status == "active"), None)
        if active is not None:
            self._activate_validation(session, active)
        else:
            session.phase = SessionPhase.COMPLETING
        event = self._event(
            session_id,
            SessionEventType.VALIDATIONS_SELECTED,
            phase_before,
            session.phase,
            selection.model_dump(mode="json"),
        )
        self._commit(session, event)
        return session.model_copy(deep=True)

    @staticmethod
    def _activate_validation(session: ResearchSession, queued) -> None:
        parent_task_id = (
            session.current_task.parent_task_id
            if session.current_task is not None and session.current_task.parent_task_id
            else session.current_task.task_id
        )
        queued.status = "active"
        session.current_task = TaskFactory.create_validation(
            parent_task_id=parent_task_id,
            task=queued.candidate.task,
        ).model_copy(update={"status": "in_progress"})
        session.phase = SessionPhase.WORKING

    def decide_plan_revision(
        self,
        session_id: str,
        decision: str,
        *,
        user_reason: str | None = None,
    ) -> ResearchSession:
        session = self._load_for_phase(
            session_id, {SessionPhase.AWAITING_PLAN_REVISION_DECISION}
        )
        if decision not in {"revise", "continue_with_warning", "end_project"}:
            raise InvariantViolationError(f"unknown plan revision decision: {decision}")
        from_working_issue = (
            session.pending_plan_issue_reason is not None
            and session.current_task is not None
            and session.current_task.status == "in_progress"
        )
        if from_working_issue:
            mentor_reason = session.pending_plan_issue_reason
        else:
            mentor_reason = (
                session.latest_complete_output.revision_reason
                if session.latest_complete_output is not None
                and session.latest_complete_output.revision_reason is not None
                else "Complete 报告当前方案需要修订"
            )
        if decision in {"continue_with_warning", "end_project"}:
            if user_reason is None or not user_reason.strip():
                raise InvariantViolationError(f"{decision} requires user_reason")
        phase_before = session.phase
        record = PlanRevisionRecord(
            decision=decision,
            mentor_reason=mentor_reason,
            user_reason=user_reason,
        )
        session.plan_revision_records.append(record)
        if decision == "revise":
            if session.current_task is None:
                raise InvariantViolationError(
                    "plan revision requires current experiment facts"
                )
            session.pending_plan_revision_context = PlanRevisionContext(
                main_experiment=(
                    session.main_experiment.model_copy(deep=True)
                    if session.main_experiment is not None
                    else None
                ),
                completed_validations=[
                    item.model_copy(deep=True)
                    for item in session.completed_validations
                ],
                current_experiment=session.current_task.experiment_info.model_copy(
                    deep=True
                ),
                mentor_issue_reason=mentor_reason,
                user_feedback=user_reason,
            )
            session.check_round = 0
            session.latest_check = None
            session.plan_decision = None
            if user_reason is not None and user_reason.strip() and session.active_plan is not None:
                session.pending_plan_feedback = UserPlanFeedback(user_reason=user_reason)
            session.phase = SessionPhase.PLANNING
        elif decision == "continue_with_warning":
            session.phase = (
                SessionPhase.WORKING
                if from_working_issue
                else SessionPhase.COMPLETING
            )
        else:
            session.phase = SessionPhase.COMPLETED
        session.pending_plan_issue_reason = None
        event = self._event(
            session_id,
            SessionEventType.PLAN_REVISION_DECIDED,
            phase_before,
            session.phase,
            record.model_dump(mode="json"),
        )
        self._commit(session, event)
        return session.model_copy(deep=True)
