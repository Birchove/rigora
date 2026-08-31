"""Atomic orchestration for idea review, planning, checking, and plan decisions."""

from datetime import date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import JsonValue

from research_mentor.agents.complete.contracts import (
    CompleteAgentInput,
    CompleteAgentOutput,
    CompleteAgentSysInput,
)
from research_mentor.agents.complete.runner import CompleteRunner
from research_mentor.agents.idea_review.contracts import IdeaReviewInput, IdeaReviewOutput, IdeaReviewSysInput
from research_mentor.agents.idea_review.runner import IdeaReviewRunner
from research_mentor.agents.key_insight_check.contracts import KeyInsightCheckInput, KeyInsightCheckSysInput
from research_mentor.agents.key_insight_check.runner import KeyInsightCheckRunner
from research_mentor.agents.plan_loop.contracts import PlanLoopInput, PlanLoopOutput, PlanLoopSysInput
from research_mentor.agents.plan_loop.runner import PlanLoopRunner
from research_mentor.agents.working_qa.contracts import (
    WorkingQAInput,
    WorkingQAOutput,
    WorkingQASysInput,
)
from research_mentor.agents.working_qa.runner import WorkingQARunner
from research_mentor.config import HarnessConfig
from research_mentor.domain.checks import KeyInsightCheckOutput
from research_mentor.domain.experiments import (
    ExperimentTaskContext,
    MainExperimentResult,
    ValidationResult,
)
from research_mentor.domain.research import (
    InitialInput,
    OverrideRecord,
    ResearchContext,
    ResearchPlan,
    UserPlanDecision,
    UserPlanFeedback,
)
from research_mentor.errors import IllegalTransitionError, InvariantViolationError
from research_mentor.harness.routing import (
    route_idea_review,
    route_complete,
    route_key_insight_check,
    route_plan_decision,
    route_working_output,
)
from research_mentor.harness.scoring import finalize_key_insight_check
from research_mentor.harness.state import ResearchSession, SessionEvent, SessionEventType, SessionPhase
from research_mentor.ports.clock import ClockPort
from research_mentor.ports.repository import ResearchSessionRepository


class ResearchMentorOrchestrator:
    def __init__(
        self,
        *,
        repository: ResearchSessionRepository,
        clock: ClockPort,
        idea_review_runner: IdeaReviewRunner,
        plan_loop_runner: PlanLoopRunner,
        key_insight_check_runner: KeyInsightCheckRunner,
        working_qa_runner: WorkingQARunner,
        complete_runner: CompleteRunner,
        config: HarnessConfig,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._idea_review_runner = idea_review_runner
        self._plan_loop_runner = plan_loop_runner
        self._key_insight_check_runner = key_insight_check_runner
        self._working_qa_runner = working_qa_runner
        self._complete_runner = complete_runner
        self._config = config

    def _load_for_phase(
        self,
        session_id: str,
        allowed: set[SessionPhase],
    ) -> ResearchSession:
        session = self._repository.get(session_id).model_copy(deep=True)
        if session.phase not in allowed:
            raise IllegalTransitionError(
                f"phase {session.phase} does not allow this command"
            )
        return session

    def _now(self) -> datetime:
        now = self._clock.now()
        if now.utcoffset() is None:
            raise InvariantViolationError("ClockPort must return a timezone-aware datetime")
        return now

    def _current_date(self) -> date:
        return self._now().astimezone(ZoneInfo("Asia/Shanghai")).date()

    def _event(
        self,
        session_id: str,
        event_type: SessionEventType,
        phase_before: SessionPhase | None,
        phase_after: SessionPhase,
        payload: dict[str, JsonValue],
    ) -> SessionEvent:
        return SessionEvent(
            event_id=str(uuid4()),
            session_id=session_id,
            event_type=event_type,
            phase_before=phase_before,
            phase_after=phase_after,
            payload=payload,
            occurred_at=self._now().isoformat(),
        )

    def _commit(self, session: ResearchSession, event: SessionEvent) -> None:
        self._repository.commit(session, event)

    def create_session(self, session_id: str) -> ResearchSession:
        session = ResearchSession(session_id=session_id)
        event = self._event(
            session_id,
            SessionEventType.SESSION_CREATED,
            None,
            session.phase,
            {},
        )
        self._repository.add(session, event)
        return session.model_copy(deep=True)

    def review_idea(self, session_id: str, idea: InitialInput) -> IdeaReviewOutput:
        session = self._load_for_phase(
            session_id,
            {SessionPhase.AWAITING_IDEA, SessionPhase.AWAITING_IDEA_REFINEMENT},
        )
        phase_before = session.phase
        output = self._idea_review_runner.run_sync(
            IdeaReviewInput(
                idea=idea.model_copy(deep=True),
                sys_input=IdeaReviewSysInput(current_date=self._current_date()),
            )
        )
        phase_after = route_idea_review(output)
        session.initial_input = idea.model_copy(deep=True)
        session.idea_review = output.model_copy(deep=True)
        session.phase = phase_after
        event = self._event(
            session_id,
            SessionEventType.IDEA_REVIEWED,
            phase_before,
            phase_after,
            output.model_dump(mode="json"),
        )
        self._commit(session, event)
        return output.model_copy(deep=True)

    def run_plan_loop(self, session_id: str) -> PlanLoopOutput:
        session = self._load_for_phase(session_id, {SessionPhase.PLANNING})
        if session.initial_input is None or session.idea_review is None:
            raise InvariantViolationError("planning requires initial_input and idea_review")

        active_plan = session.active_plan
        latest_check = session.latest_check
        feedback = session.pending_plan_feedback
        if active_plan is None and latest_check is None and feedback is None:
            mode = "initial"
            is_initial = True
            previous_plan = None
            previous_check = None
            user_feedback = None
        elif active_plan is not None and latest_check is not None and feedback is None:
            mode = "check_revision"
            is_initial = False
            previous_plan = active_plan
            previous_check = latest_check
            user_feedback = None
        elif active_plan is not None and latest_check is None and feedback is not None:
            mode = "user_revision"
            is_initial = False
            previous_plan = active_plan
            previous_check = None
            user_feedback = feedback
        else:
            raise InvariantViolationError("planning session has an invalid revision-input combination")

        phase_before = session.phase
        output = self._plan_loop_runner.run_sync(
            PlanLoopInput(
                idea=session.initial_input.model_copy(deep=True),
                sys_input=PlanLoopSysInput(current_date=self._current_date()),
                review_result=session.idea_review.model_copy(deep=True),
                check_round=session.check_round,
                max_check_rounds=self._config.max_check_rounds,
                previous_insight_check=(
                    previous_check.model_copy(deep=True) if previous_check else None
                ),
                previous_plan=previous_plan.model_copy(deep=True) if previous_plan else None,
                user_feedback=user_feedback.model_copy(deep=True) if user_feedback else None,
            )
        )
        if is_initial and output.change_summary:
            raise InvariantViolationError(
                f"{mode} plan output must not contain change_summary"
            )
        phase_after = SessionPhase.CHECKING_KEY_INSIGHT
        session.latest_plan_output = output.model_copy(deep=True)
        session.active_plan = output.plan.model_copy(deep=True)
        session.latest_check = None
        session.pending_plan_feedback = None
        session.phase = phase_after
        event = self._event(
            session_id,
            SessionEventType.PLAN_GENERATED,
            phase_before,
            phase_after,
            output.model_dump(mode="json"),
        )
        self._commit(session, event)
        return output.model_copy(deep=True)

    def run_key_insight_check(self, session_id: str) -> KeyInsightCheckOutput:
        session = self._load_for_phase(session_id, {SessionPhase.CHECKING_KEY_INSIGHT})
        if (
            session.initial_input is None
            or session.idea_review is None
            or session.latest_plan_output is None
            or session.active_plan is None
        ):
            raise InvariantViolationError(
                "key insight check requires idea, review, plan output, and active plan"
            )
        if session.check_round < 0 or session.check_round >= self._config.max_check_rounds:
            raise InvariantViolationError("check_round is outside the callable range")
        if session.latest_check is not None or session.pending_plan_feedback is not None:
            raise InvariantViolationError("checking session contains stale revision state")

        phase_before = session.phase
        session.check_round += 1
        assessment = self._key_insight_check_runner.run_sync(
            KeyInsightCheckInput(
                idea=session.initial_input.model_copy(deep=True),
                sys_input=KeyInsightCheckSysInput(current_date=self._current_date()),
                review_result=session.idea_review.model_copy(deep=True),
                key_insight_input=session.latest_plan_output.model_copy(deep=True),
                plan=session.active_plan.model_copy(deep=True),
                previous_check_feedback=None,
            )
        )
        output = finalize_key_insight_check(assessment, self._config)
        phase_after = route_key_insight_check(
            output,
            check_round=session.check_round,
            max_check_rounds=self._config.max_check_rounds,
        )
        session.latest_check = output.model_copy(deep=True)
        session.phase = phase_after
        event = self._event(
            session_id,
            SessionEventType.KEY_INSIGHT_CHECKED,
            phase_before,
            phase_after,
            output.model_dump(mode="json"),
        )
        self._commit(session, event)
        return output.model_copy(deep=True)

    def decide_plan(
        self,
        session_id: str,
        decision: UserPlanDecision,
    ) -> ResearchSession:
        session = self._load_for_phase(
            session_id, {SessionPhase.AWAITING_PLAN_DECISION}
        )
        if (
            session.active_plan is None
            or session.latest_plan_output is None
            or session.latest_check is None
            or not session.latest_check.check_decision
        ):
            raise InvariantViolationError("plan decision requires a passing active plan and check")

        phase_before = session.phase
        phase_after = route_plan_decision(decision)
        payload = decision.model_dump(mode="json")
        if decision.decision == "request_revision":
            if decision.user_reason is None:
                raise InvariantViolationError("request_revision requires user_reason")
            session.pending_plan_feedback = UserPlanFeedback(user_reason=decision.user_reason)
            session.check_round = 0
            session.latest_check = None
            session.plan_decision = None
        else:
            session.plan_decision = decision.model_copy(deep=True)
            if decision.decision == "override":
                if decision.overridden_key_insight is None:
                    raise InvariantViolationError("override requires overridden_key_insight")
                record = OverrideRecord(
                    agent_recommendation=session.active_plan.key_insight.model_copy(deep=True),
                    user_choice=decision.overridden_key_insight.model_copy(deep=True),
                    agent_reason=session.latest_check.decision_reason,
                    user_reason=decision.user_reason,
                    timestamp=self._now().isoformat(),
                )
                session.active_plan = session.active_plan.model_copy(
                    update={"key_insight": decision.overridden_key_insight.model_copy(deep=True)}
                )
                session.latest_plan_output = session.latest_plan_output.model_copy(
                    update={
                        "plan": session.latest_plan_output.plan.model_copy(
                            update={
                                "key_insight": decision.overridden_key_insight.model_copy(deep=True)
                            }
                        )
                    }
                )
                session.override_record = record
                payload["override_record"] = record.model_dump(mode="json")
        session.phase = phase_after
        event = self._event(
            session_id,
            SessionEventType.PLAN_DECIDED,
            phase_before,
            phase_after,
            payload,
        )
        self._commit(session, event)
        return session.model_copy(deep=True)

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
            if plan is None:
                raise InvariantViolationError("forward working requires an explicit plan")
            session.active_plan = plan.model_copy(deep=True)
            payload = task_context.model_dump(mode="json")
            payload["active_plan"] = plan.model_dump(mode="json")
        else:
            if plan is not None:
                raise InvariantViolationError("accepted working plan cannot be replaced")
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
    ) -> WorkingQAOutput:
        session = self._load_for_phase(session_id, {SessionPhase.WORKING})
        if (
            session.initial_input is None
            or session.idea_review is None
            or session.active_plan is None
            or session.current_task is None
        ):
            raise InvariantViolationError(
                "working QA requires initial_input, idea_review, active_plan, and current_task"
            )

        phase_before = session.phase
        output = self._working_qa_runner.run_sync(
            WorkingQAInput(
                idea=session.initial_input.model_copy(deep=True),
                question=question,
                sys_input=WorkingQASysInput(current_date=self._current_date()),
                research_context=ResearchContext(
                    normalized_idea=session.idea_review.normalized_idea,
                    research_question=session.active_plan.research_question,
                    plan=session.active_plan.model_copy(deep=True),
                ),
                task_context=session.current_task.model_copy(deep=True),
                conversation_turns=[],
                compact_context=None,
            )
        )
        if output.updated_experiment_info is not None:
            session.current_task = session.current_task.model_copy(
                update={
                    "experiment_info": output.updated_experiment_info.model_copy(deep=True)
                }
            )
        phase_after = route_working_output(output)
        if output.action == "success":
            session.current_task = session.current_task.model_copy(
                update={"status": "completed"}
            )
        session.phase = phase_after
        event = self._event(
            session_id,
            SessionEventType.WORKING_TURN_COMPLETED,
            phase_before,
            phase_after,
            output.model_dump(mode="json"),
        )
        self._commit(session, event)
        return output.model_copy(deep=True)

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
        if session.current_task.status != "completed":
            raise InvariantViolationError("result recording requires a completed task")

        phase_before = session.phase
        session.main_experiment = result.model_copy(deep=True)
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
        if session.current_task.status != "completed":
            raise InvariantViolationError("result recording requires a completed task")
        if session.main_experiment is None:
            raise InvariantViolationError("validation result requires a main experiment")

        phase_before = session.phase
        session.completed_validations.append(result.model_copy(deep=True))
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

    def run_complete(
        self,
        session_id: str,
        completion_status: bool,
    ) -> CompleteAgentOutput:
        session = self._load_for_phase(session_id, {SessionPhase.COMPLETING})
        if (
            session.initial_input is None
            or session.idea_review is None
            or session.active_plan is None
            or session.main_experiment is None
        ):
            raise InvariantViolationError(
                "completion requires initial_input, idea_review, active_plan, and main_experiment"
            )

        phase_before = session.phase
        output = self._complete_runner.run_sync(
            CompleteAgentInput(
                idea=session.initial_input.model_copy(deep=True),
                normalized_idea=session.idea_review.normalized_idea,
                sys_input=CompleteAgentSysInput(
                    current_date=self._current_date(), completion_status=completion_status
                ),
                plan=session.active_plan.model_copy(deep=True),
                main_experiment=session.main_experiment.model_copy(deep=True),
                completed_validations=[
                    result.model_copy(deep=True)
                    for result in session.completed_validations
                ],
            )
        )
        phase_after = route_complete(output).next_phase
        session.latest_complete_output = output.model_copy(deep=True)
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
