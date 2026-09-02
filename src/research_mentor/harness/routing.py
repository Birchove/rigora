"""Pure deterministic routing for Harness state transitions."""

from pydantic import BaseModel

from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.agents.working_qa.contracts import WorkingQAOutput
from research_mentor.domain.completion import CompleteAgentOutput
from research_mentor.domain.checks import KeyInsightCheckOutput
from research_mentor.domain.research import UserPlanDecision
from research_mentor.errors import InvariantViolationError
from research_mentor.harness.state import SessionPhase


class RoutingDecision(BaseModel):
    next_phase: SessionPhase
    reason: str


def route_idea_review(output: IdeaReviewOutput) -> SessionPhase:
    legal_combinations = {
        ("opinion", "proceed_to_plan"),
        ("opinion", "request_refinement"),
        ("opinion", "reject"),
        ("range", "request_refinement"),
        ("forward", "proceed_to_working"),
        ("forward", "request_refinement"),
        ("forward", "reject"),
    }
    combination = (output.idea_type, output.action)
    if combination not in legal_combinations:
        raise InvariantViolationError(
            f"非法的 idea_type/action 组合: {output.idea_type}/{output.action}"
        )
    if output.action == "proceed_to_plan":
        return SessionPhase.PLANNING
    if output.action == "proceed_to_working":
        return SessionPhase.WORKING
    if output.action == "request_refinement":
        return SessionPhase.AWAITING_IDEA_REFINEMENT
    return SessionPhase.REJECTED


def route_key_insight_check(
    output: KeyInsightCheckOutput,
    *,
    check_round: int,
    max_check_rounds: int,
) -> SessionPhase:
    if check_round < 1 or check_round > max_check_rounds:
        raise InvariantViolationError("check_round 超出合法范围")
    if output.check_decision:
        return SessionPhase.AWAITING_PLAN_DECISION
    if check_round < max_check_rounds:
        return SessionPhase.PLANNING
    return SessionPhase.CHECK_LOOP_EXHAUSTED


def route_plan_decision(
    decision: UserPlanDecision,
) -> SessionPhase:
    if decision.decision in {"accept", "override"}:
        return SessionPhase.AWAITING_WORKING_CONTEXT
    if decision.decision == "request_revision":
        return SessionPhase.PLANNING
    raise InvariantViolationError(f"未知的 plan decision: {decision.decision}")


def route_working_output(
    output: WorkingQAOutput,
) -> SessionPhase:
    if output.action == "report_plan_issue":
        return SessionPhase.AWAITING_PLAN_REVISION_DECISION
    if output.action in {"answer", "clarify", "decline"}:
        return SessionPhase.WORKING
    raise InvariantViolationError(
        f"非法 working action {output.action!r}；允许: answer, clarify, decline, report_plan_issue"
    )


def route_complete(output: CompleteAgentOutput) -> RoutingDecision:
    phase_by_mode = {
        "validation": SessionPhase.AWAITING_VALIDATION_SELECTION,
        "plan_revision": SessionPhase.AWAITING_PLAN_REVISION_DECISION,
        "writing": SessionPhase.COMPLETED,
    }
    return RoutingDecision(
        next_phase=phase_by_mode[output.mode],
        reason=output.final_hint,
    )
