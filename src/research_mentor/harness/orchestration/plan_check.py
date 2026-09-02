"""Plan generation, key-insight check, and plan-decision orchestration."""

from research_mentor.agents.key_insight_check.contracts import KeyInsightCheckInput, KeyInsightCheckSysInput
from research_mentor.agents.plan_loop.contracts import (
    PlanLoopInput,
    PlanLoopOutput,
    PlanLoopSysInput,
    resolve_plan_loop_mode,
)
from research_mentor.domain.checks import CheckRound, KeyInsightCheckOutput
from research_mentor.domain.research import (
    OverrideRecord,
    PlanCandidateOverrideRecord,
    PlanCandidatePath,
    PlanGenerationMode,
    ResearchContext,
    UserPlanDecision,
    UserPlanFeedback,
)
from research_mentor.errors import InvariantViolationError
from research_mentor.harness.orchestration.base import OrchestratorBase
from research_mentor.harness.routing import route_key_insight_check, route_plan_decision
from research_mentor.harness.scoring import finalize_key_insight_check
from research_mentor.harness.state import ResearchSession, SessionEventType, SessionPhase
from research_mentor.harness.task_factory import TaskFactory
from research_mentor.hyperparameters import PLAN_CANDIDATE_COUNTS, PLAN_CANDIDATE_FOCUS_HINTS


class PlanCheckOrchestrator(OrchestratorBase):
    def run_plan_loop(self, session_id: str) -> PlanLoopOutput:
        session = self._load_for_phase(session_id, {SessionPhase.PLANNING})
        if session.initial_input is None or session.idea_review is None:
            raise InvariantViolationError("planning requires initial_input and idea_review")

        active_plan = session.active_plan
        latest_check = session.latest_check
        feedback = session.pending_plan_feedback
        revision_context = session.pending_plan_revision_context
        try:
            mode = resolve_plan_loop_mode(
                previous_plan=active_plan,
                previous_insight_check=latest_check,
                user_feedback=feedback,
                revision_context=revision_context,
            )
        except ValueError as exc:
            raise InvariantViolationError(
                "planning session has an invalid revision-input combination"
            ) from exc
        is_initial = mode == "initial"
        previous_plan = None if is_initial else active_plan
        previous_check = latest_check if mode == "check_revision" else None
        user_feedback = feedback if mode in {"user_revision", "result_revision"} else None

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
            ),
            model_profile=self._config.plan_model_for_path(0),
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
        count_by_mode = PLAN_CANDIDATE_COUNTS
        focus_hints = PLAN_CANDIDATE_FOCUS_HINTS
        candidates: list[PlanCandidatePath] = []
        outputs: list[PlanLoopOutput] = []
        for index in range(count_by_mode[mode]):
            plan_model = self._config.plan_model_for_path(index)
            check_model = self._config.check_model_for_path(index)
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
                ),
                model_profile=plan_model,
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
                    plan_model_profile=plan_model,
                    check_model_profile=check_model,
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
            ),
            model_profile=candidate.plan_model_profile,
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
            ),
            model_profile=candidate.check_model_profile,
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
            ),
            model_profile=self._config.check_model_for_path(0),
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
