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
from research_mentor.agents.plan_loop.contracts import (
    PlanLoopInput,
    PlanLoopOutput,
    PlanLoopSysInput,
    PlanRevisionContext,
)
from research_mentor.agents.plan_loop.runner import PlanLoopRunner
from research_mentor.agents.working_qa.contracts import (
    WorkingQAInput,
    WorkingQAOutput,
    WorkingQASysInput,
)
from research_mentor.agents.working_qa.runner import WorkingQARunner
from research_mentor.config import HarnessConfig
from research_mentor.domain.checks import CheckRound, KeyInsightCheckOutput
from research_mentor.domain.experiments import (
    ExperimentTaskContext,
    MainExperimentResult,
    ValidationResult,
)
from research_mentor.domain.research import (
    InitialInput,
    OverrideRecord,
    PlanCandidatePath,
    PlanCandidateOverrideRecord,
    PlanGenerationMode,
    ResearchContext,
    ResearchPlan,
    UserPlanDecision,
    UserPlanFeedback,
)
from research_mentor.domain.completion import ValidationSelection
from research_mentor.errors import IllegalTransitionError, InvariantViolationError
from research_mentor.harness.routing import (
    route_idea_review,
    route_complete,
    route_key_insight_check,
    route_plan_decision,
    route_working_output,
)
from research_mentor.harness.scoring import finalize_key_insight_check
from research_mentor.harness.state import PlanRevisionRecord, ResearchSession, SessionEvent, SessionEventType, SessionPhase
from research_mentor.harness.task_factory import TaskFactory
from research_mentor.harness.validation import (
    ValidationQueue,
    validation_task_identity,
)
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
        supported_domains = {
            item.casefold()
            for item in (
                *self._config.supported_domains,
                *self._config.supported_domain_aliases,
            )
        }
        if idea.domain.strip().casefold() not in supported_domains:
            output = IdeaReviewOutput(
                idea_type="range",
                action="request_refinement",
                normalized_idea=idea.original_idea,
                reason="当前版本仅支持 computer science 领域。",
                next_action="请将问题限定为 computer science 研究，或使用通用 Agent。",
            )
            refinement_code = "unsupported_domain"
        else:
            output = self._idea_review_runner.run_sync(
                IdeaReviewInput(
                    idea=idea.model_copy(deep=True),
                    sys_input=IdeaReviewSysInput(current_date=self._current_date()),
                )
            )
            refinement_code = (
                "idea_refinement" if output.action == "request_refinement" else None
            )
        phase_after = route_idea_review(output)
        session.initial_input = idea.model_copy(deep=True)
        session.idea_review = output.model_copy(deep=True)
        session.refinement_code = refinement_code
        if output.action == "proceed_to_working":
            if output.forward_context is None:
                raise InvariantViolationError("forward working requires forward_context")
            session.research_context = ResearchContext(
                normalized_idea=output.normalized_idea,
                research_question=output.forward_context.research_question,
                forward_context=output.forward_context.model_copy(deep=True),
            )
            session.current_task = TaskFactory.from_forward_context(
                output.forward_context
            )
            session.main_experiment = (
                output.forward_context.main_result.model_copy(deep=True)
                if output.forward_context.main_result is not None
                else None
            )
            session.completed_validations = [
                item.model_copy(deep=True)
                for item in output.forward_context.completed_validations
            ]
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
        revision_context = session.pending_plan_revision_context
        if revision_context is not None:
            mode = "result_revision"
            is_initial = active_plan is None
            previous_plan = active_plan
            previous_check = None
            user_feedback = feedback
        elif active_plan is None and latest_check is None and feedback is None:
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
                revision_context=(
                    session.pending_plan_revision_context.model_copy(deep=True)
                    if session.pending_plan_revision_context is not None
                    else None
                ),
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
        session.pending_plan_revision_context = None
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

    def run_plan(
        self,
        session_id: str,
        *,
        mode: PlanGenerationMode = "low",
        candidate_id: str | None = None,
    ) -> ResearchSession:
        session = self._load_for_phase(session_id, {SessionPhase.PLANNING})
        if session.initial_input is None or session.idea_review is None:
            raise InvariantViolationError("planning requires initial_input and idea_review")
        if session.plan_candidates:
            return self._revise_candidate_plan(session, candidate_id)
        count_by_mode = {"low": 1, "mid": 2, "high": 3}
        focus_hints = (
            "最小可行、风险受控的验证路径",
            "强调研究增量与对照解释的平衡路径",
            "强调高信息增益与关键假设压力测试的路径",
        )
        candidates: list[PlanCandidatePath] = []
        outputs: list[PlanLoopOutput] = []
        for index in range(count_by_mode[mode]):
            output = self._plan_loop_runner.run_sync(
                PlanLoopInput(
                    idea=session.initial_input.model_copy(deep=True),
                    sys_input=PlanLoopSysInput(current_date=self._current_date()),
                    review_result=session.idea_review.model_copy(deep=True),
                    check_round=0,
                    max_check_rounds=self._config.max_check_rounds,
                    candidate_index=index + 1,
                    candidate_focus=focus_hints[index],
                    revision_context=(
                        session.pending_plan_revision_context.model_copy(deep=True)
                        if session.pending_plan_revision_context is not None
                        else None
                    ),
                )
            )
            if output.change_summary:
                raise InvariantViolationError(
                    "initial candidate plan must not contain change_summary"
                )
            outputs.append(output)
            candidates.append(
                PlanCandidatePath(
                    candidate_id=f"candidate-{index + 1}",
                    candidate_index=index + 1,
                    model_profile=f"plan-{mode}-{index + 1}",
                    focus_hint=focus_hints[index],
                    plan=output.plan.model_copy(deep=True),
                    response_to_user=output.response_to_user,
                )
            )
        phase_before = session.phase
        session.plan_generation_mode = mode
        session.plan_candidates = candidates
        session.latest_plan_output = outputs[0].model_copy(deep=True)
        session.active_plan = outputs[0].plan.model_copy(deep=True)
        session.pending_plan_revision_context = None
        session.phase = SessionPhase.CHECKING_KEY_INSIGHT
        event = self._event(
            session_id,
            SessionEventType.PLAN_GENERATED,
            phase_before,
            session.phase,
            {
                "mode": mode,
                "candidates": [item.model_dump(mode="json") for item in candidates],
            },
        )
        self._commit(session, event)
        return session.model_copy(deep=True)

    def _revise_candidate_plan(
        self,
        session: ResearchSession,
        candidate_id: str | None,
    ) -> ResearchSession:
        revision_context = session.pending_plan_revision_context
        if candidate_id is None:
            default_disposition = (
                "selected" if revision_context is not None else "active"
            )
            candidates = [
                item
                for item in session.plan_candidates
                if item.disposition == default_disposition
            ]
            if len(candidates) != 1:
                raise InvariantViolationError("candidate_id is required for revision")
            candidate = candidates[0]
        else:
            candidate = next(
                (
                    item
                    for item in session.plan_candidates
                    if item.candidate_id == candidate_id
                ),
                None,
            )
        if candidate is None or candidate.plan is None:
            raise InvariantViolationError("unknown candidate_id")
        previous_check = (
            candidate.check_history[-1].output if candidate.check_history else None
        )
        user_feedback = session.pending_plan_feedback
        if (
            revision_context is None
            and previous_check is None
            and user_feedback is None
        ):
            raise InvariantViolationError("candidate revision requires feedback")
        output = self._plan_loop_runner.run_sync(
            PlanLoopInput(
                idea=session.initial_input.model_copy(deep=True),
                sys_input=PlanLoopSysInput(current_date=self._current_date()),
                review_result=session.idea_review.model_copy(deep=True),
                check_round=candidate.check_round,
                max_check_rounds=self._config.max_check_rounds,
                previous_plan=candidate.plan.model_copy(deep=True),
                previous_insight_check=(
                    previous_check.model_copy(deep=True)
                    if revision_context is None
                    and user_feedback is None
                    and previous_check is not None
                    else None
                ),
                user_feedback=(
                    user_feedback.model_copy(deep=True)
                    if revision_context is None and user_feedback is not None
                    else None
                ),
                candidate_index=candidate.candidate_index,
                candidate_focus=candidate.focus_hint,
                revision_context=(
                    revision_context.model_copy(deep=True)
                    if revision_context is not None
                    else None
                ),
            )
        )
        candidate.plan = output.plan.model_copy(deep=True)
        candidate.response_to_user = output.response_to_user
        candidate.change_summary = list(output.change_summary)
        if revision_context is not None:
            candidate.disposition = "active"
            candidate.check_round = 0
            candidate.check_history = []
        session.pending_plan_feedback = None
        session.pending_plan_revision_context = None
        session.active_plan = candidate.plan.model_copy(deep=True)
        session.latest_plan_output = output.model_copy(deep=True)
        session.phase = SessionPhase.CHECKING_KEY_INSIGHT
        event = self._event(
            session.session_id,
            SessionEventType.PLAN_GENERATED,
            SessionPhase.PLANNING,
            session.phase,
            {"candidate_id": candidate.candidate_id, **output.model_dump(mode="json")},
        )
        self._commit(session, event)
        return session.model_copy(deep=True)

    def run_check(
        self,
        session_id: str,
        *,
        candidate_id: str | None = None,
    ) -> ResearchSession:
        session = self._load_for_phase(
            session_id, {SessionPhase.CHECKING_KEY_INSIGHT}
        )
        if session.initial_input is None or session.idea_review is None:
            raise InvariantViolationError("checking requires idea and review")
        if not session.plan_candidates:
            raise InvariantViolationError("checking requires candidate paths")
        if candidate_id is None:
            if len(session.plan_candidates) != 1:
                raise InvariantViolationError("candidate_id is required for multiple paths")
            candidate_id = session.plan_candidates[0].candidate_id
        candidate = next(
            (item for item in session.plan_candidates if item.candidate_id == candidate_id),
            None,
        )
        if candidate is None:
            raise InvariantViolationError("unknown candidate_id")
        if candidate.plan is None or candidate.disposition != "active":
            raise InvariantViolationError("candidate is not ready for check")
        if candidate.check_round >= self._config.max_check_rounds:
            raise InvariantViolationError("candidate check limit reached")
        assessment = self._key_insight_check_runner.run_sync(
            KeyInsightCheckInput(
                idea=session.initial_input.model_copy(deep=True),
                sys_input=KeyInsightCheckSysInput(current_date=self._current_date()),
                review_result=session.idea_review.model_copy(deep=True),
                key_insight_input=PlanLoopOutput(
                    plan=candidate.plan.model_copy(deep=True),
                    change_summary=list(candidate.change_summary),
                    response_to_user=candidate.response_to_user or "候选方案",
                ),
                plan=candidate.plan.model_copy(deep=True),
                previous_check_feedback=None,
            )
        )
        output = finalize_key_insight_check(assessment, self._config)
        candidate.check_round += 1
        candidate.check_history.append(
            CheckRound(
                check_round=candidate.check_round,
                output=output.model_copy(deep=True),
                final_score=output.final_score,
                passed=output.check_decision,
            )
        )
        if output.check_decision:
            candidate.disposition = "ready"
        elif candidate.check_round >= self._config.max_check_rounds:
            candidate.disposition = "exhausted"
        else:
            session.phase = SessionPhase.PLANNING
        participating_candidates = [
            item
            for item in session.plan_candidates
            if item.disposition != "archived"
        ]
        if all(
            item.disposition in {"ready", "exhausted", "override"}
            for item in participating_candidates
        ):
            session.phase = (
                SessionPhase.AWAITING_PLAN_DECISION
                if any(
                    item.disposition in {"ready", "override"}
                    for item in participating_candidates
                )
                else SessionPhase.CHECK_LOOP_EXHAUSTED
            )
        elif candidate.disposition == "ready":
            session.phase = SessionPhase.CHECKING_KEY_INSIGHT
        session.latest_check = output.model_copy(deep=True)
        event = self._event(
            session_id,
            SessionEventType.KEY_INSIGHT_CHECKED,
            SessionPhase.CHECKING_KEY_INSIGHT,
            session.phase,
            {"candidate_id": candidate_id, **output.model_dump(mode="json")},
        )
        self._commit(session, event)
        return session.model_copy(deep=True)

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
        *,
        candidate_id: str | None = None,
    ) -> ResearchSession:
        session = self._load_for_phase(
            session_id, {SessionPhase.AWAITING_PLAN_DECISION}
        )
        if session.plan_candidates:
            return self._decide_candidate_plan(session, decision, candidate_id)
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

    def _decide_candidate_plan(
        self,
        session: ResearchSession,
        decision: UserPlanDecision,
        candidate_id: str | None,
    ) -> ResearchSession:
        if candidate_id is None:
            if len(session.plan_candidates) != 1:
                raise InvariantViolationError("candidate_id is required for multiple paths")
            candidate_id = session.plan_candidates[0].candidate_id
        candidate = next(
            (item for item in session.plan_candidates if item.candidate_id == candidate_id),
            None,
        )
        if candidate is None:
            raise InvariantViolationError("unknown candidate_id")
        if candidate.disposition not in {"ready", "override"} or candidate.plan is None:
            raise InvariantViolationError("selected candidate is not ready")
        if not candidate.check_history:
            raise InvariantViolationError("selected candidate requires check history")
        if session.idea_review is None:
            raise InvariantViolationError("selected candidate requires idea review")
        phase_before = session.phase
        payload = {"candidate_id": candidate_id, **decision.model_dump(mode="json")}
        if decision.decision == "request_revision":
            if decision.user_reason is None:
                raise InvariantViolationError("request_revision requires user_reason")
            candidate.disposition = "active"
            candidate.check_round = 0
            candidate.check_history = []
            session.pending_plan_feedback = UserPlanFeedback(
                user_reason=decision.user_reason
            )
            session.phase = SessionPhase.PLANNING
        else:
            selected_plan = candidate.plan.model_copy(deep=True)
            if decision.decision == "override":
                if decision.overridden_key_insight is None:
                    raise InvariantViolationError(
                        "override requires overridden_key_insight"
                    )
                record = OverrideRecord(
                    agent_recommendation=selected_plan.key_insight.model_copy(
                        deep=True
                    ),
                    user_choice=decision.overridden_key_insight.model_copy(deep=True),
                    agent_reason=candidate.check_history[-1].output.decision_reason,
                    user_reason=decision.user_reason,
                    timestamp=self._now().isoformat(),
                )
                selected_plan = selected_plan.model_copy(
                    update={
                        "key_insight": decision.overridden_key_insight.model_copy(
                            deep=True
                        )
                    }
                )
                session.override_record = record
                payload["override_record"] = record.model_dump(mode="json")
            for item in session.plan_candidates:
                if item.candidate_id == candidate_id:
                    item.disposition = "selected"
                    item.plan = selected_plan.model_copy(deep=True)
                elif item.disposition == "ready":
                    item.disposition = "archived"
            session.active_plan = selected_plan
            session.latest_plan_output = PlanLoopOutput(
                plan=selected_plan.model_copy(deep=True),
                change_summary=list(candidate.change_summary),
                response_to_user=candidate.response_to_user or "已选择候选方案",
            )
            session.latest_check = candidate.check_history[-1].output.model_copy(
                deep=True
            )
            session.plan_decision = decision.model_copy(deep=True)
            session.current_task = TaskFactory.from_plan(selected_plan)
            session.research_context = ResearchContext(
                normalized_idea=session.idea_review.normalized_idea,
                research_question=selected_plan.research_question,
                plan=selected_plan.model_copy(deep=True),
            )
            session.phase = SessionPhase.WORKING
        event = self._event(
            session.session_id,
            SessionEventType.PLAN_DECIDED,
            phase_before,
            session.phase,
            payload,
        )
        self._commit(session, event)
        return session.model_copy(deep=True)

    def continue_imperfect_plan(
        self,
        session_id: str,
        candidate_id: str,
        *,
        user_reason: str,
    ) -> ResearchSession:
        session = self._load_for_phase(
            session_id,
            {SessionPhase.CHECK_LOOP_EXHAUSTED, SessionPhase.AWAITING_PLAN_DECISION},
        )
        candidate = next(
            (item for item in session.plan_candidates if item.candidate_id == candidate_id),
            None,
        )
        if candidate is None or candidate.disposition != "exhausted":
            raise InvariantViolationError("candidate is not exhausted")
        if not user_reason.strip():
            raise InvariantViolationError("override requires user_reason")
        phase_before = session.phase
        last_check = candidate.check_history[-1]
        candidate.disposition = "override"
        session.candidate_override_records.append(
            PlanCandidateOverrideRecord(
                candidate_id=candidate_id,
                final_score=last_check.final_score,
                unresolved_issues=list(last_check.output.revision_request),
                user_reason=user_reason,
                timestamp=self._now().isoformat(),
            )
        )
        session.phase = SessionPhase.AWAITING_PLAN_DECISION
        event = self._event(
            session_id,
            SessionEventType.PLAN_DECIDED,
            phase_before,
            session.phase,
            {
                "candidate_id": candidate_id,
                "decision": "continue_imperfect",
                "user_reason": user_reason,
            },
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
        output = self._working_qa_runner.run_sync(
            WorkingQAInput(
                idea=session.initial_input.model_copy(deep=True),
                question=question,
                sys_input=WorkingQASysInput(current_date=self._current_date()),
                research_context=session.research_context.model_copy(deep=True),
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
        if output.action == "report_plan_issue" and session.current_task.task_kind != "main":
            raise InvariantViolationError("only a main task may report a plan issue")
        if output.action == "report_plan_issue":
            session.pending_plan_issue_reason = output.reason
        phase_after = route_working_output(output)
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
            )
        )
        phase_after = route_complete(output).next_phase
        session.latest_complete_output = output.model_copy(deep=True)
        if output.mode == "validation":
            handled_ids = set()
            handled_task_identities = set()
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
                handled_task_identities = {
                    validation_task_identity(item.candidate.task)
                    for item in handled
                }
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
        mentor_reason = (
            session.latest_complete_output.revision_reason
            if session.latest_complete_output is not None
            and session.latest_complete_output.revision_reason is not None
            else session.pending_plan_issue_reason
            or "Working 报告当前方案存在关键问题"
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
                SessionPhase.COMPLETING
                if session.main_experiment is not None
                else SessionPhase.WORKING
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
