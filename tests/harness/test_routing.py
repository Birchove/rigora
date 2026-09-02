import ast
import inspect
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.agents.working_qa.contracts import WorkingQAOutput
from research_mentor.domain.completion import CompleteAgentOutput
from research_mentor.domain.checks import (
    DimensionScore,
    KeyInsightAssessment,
    KeyInsightCheckOutput,
    KeyInsightDiagnostics,
    KeyInsightScores,
)
from research_mentor.domain.experiments import ExperimentInfo
from research_mentor.domain.research import (
    ForwardResearchContext,
    KeyInsight,
    UserPlanDecision,
)
from research_mentor.errors import InvariantViolationError
from research_mentor.harness.routing import (
    RoutingDecision,
    route_complete,
    route_idea_review,
    route_key_insight_check,
    route_plan_decision,
    route_working_output,
)
from research_mentor.harness.state import SessionPhase


def idea_output_factory(idea_type: str, action: str) -> IdeaReviewOutput:
    payload = {
        "idea_type": idea_type,
        "action": action,
        "normalized_idea": "可验证的研究主张",
        "reason": "理由",
        "next_action": "下一步",
    }
    if idea_type == "forward" and action == "proceed_to_working":
        payload["forward_context"] = ForwardResearchContext(
            stage="experiment_in_progress",
            research_question="状态压缩能否提升恢复稳定性？",
            current_experiment=ExperimentInfo(current_experiment="主实验"),
        )
    return IdeaReviewOutput(**payload)


def unvalidated_idea_output(idea_type: str, action: str) -> IdeaReviewOutput:
    return IdeaReviewOutput.model_construct(
        idea_type=idea_type,
        action=action,
        normalized_idea="可验证的研究主张",
        reason="理由",
        next_action="下一步",
    )


def check_output_factory(check_decision: bool) -> KeyInsightCheckOutput:
    dimension_names = (
        "research_fit",
        "novelty",
        "research_value",
        "testability_feasibility",
        "evidence_support",
    )
    scores = KeyInsightScores(
        **{
            name: DimensionScore(score=7.0, reason="评分理由")
            for name in dimension_names
        }
    )
    assessment = KeyInsightAssessment(
        diagnostics=KeyInsightDiagnostics(
            core_claim="核心主张",
            expected_contribution="预期贡献",
            validation_path="验证路径",
        ),
        scores=scores,
        reason="评估理由",
        summary_advice="建议",
    )
    return KeyInsightCheckOutput(
        assessment=assessment,
        final_score=7.0,
        check_decision=check_decision,
        decision_reason="检查理由",
        scoring_rule_version="v1",
    )


def key_insight() -> KeyInsight:
    return KeyInsight(title="点睛之笔", content="内容", rationale="理由")


def decision_factory(decision: str) -> UserPlanDecision:
    if decision == "accept":
        return UserPlanDecision(decision=decision)
    if decision == "override":
        return UserPlanDecision(decision=decision, overridden_key_insight=key_insight())
    return UserPlanDecision(decision=decision, user_reason="修订理由")


def working_output_factory(action: str) -> WorkingQAOutput:
    return WorkingQAOutput(
        action=action,
        reason="处理理由",
        reply="处理回复",
    )


@pytest.mark.parametrize(
    ("idea_type", "action", "phase"),
    [
        ("opinion", "proceed_to_plan", SessionPhase.PLANNING),
        ("opinion", "request_refinement", SessionPhase.AWAITING_IDEA_REFINEMENT),
        ("opinion", "reject", SessionPhase.REJECTED),
        ("range", "request_refinement", SessionPhase.AWAITING_IDEA_REFINEMENT),
        ("forward", "proceed_to_working", SessionPhase.WORKING),
        ("forward", "request_refinement", SessionPhase.AWAITING_IDEA_REFINEMENT),
        ("forward", "reject", SessionPhase.REJECTED),
    ],
)
def test_idea_routes(idea_type: str, action: str, phase: SessionPhase) -> None:
    assert route_idea_review(idea_output_factory(idea_type, action)) is phase


@pytest.mark.parametrize(
    ("idea_type", "action"),
    [
        ("opinion", "proceed_to_working"),
        ("range", "proceed_to_plan"),
        ("range", "proceed_to_working"),
        ("range", "reject"),
        ("forward", "proceed_to_plan"),
    ],
)
def test_idea_table_out_combinations_are_rejected(
    idea_type: str, action: str
) -> None:
    with pytest.raises(InvariantViolationError):
        route_idea_review(unvalidated_idea_output(idea_type, action))


@pytest.mark.parametrize("check_round", [1, 2, 3, 4, 5])
def test_check_pass_waits_for_plan_decision(check_round: int) -> None:
    output = check_output_factory(True)
    assert (
        route_key_insight_check(output, check_round=check_round, max_check_rounds=5)
        is SessionPhase.AWAITING_PLAN_DECISION
    )


@pytest.mark.parametrize("check_round", [1, 2, 3, 4])
def test_check_fail_rounds_one_to_four_return_to_planning(check_round: int) -> None:
    output = check_output_factory(False)
    assert (
        route_key_insight_check(output, check_round=check_round, max_check_rounds=5)
        is SessionPhase.PLANNING
    )


def test_fifth_failed_check_exhausts_loop() -> None:
    assert (
        route_key_insight_check(
            check_output_factory(False), check_round=5, max_check_rounds=5
        )
        is SessionPhase.CHECK_LOOP_EXHAUSTED
    )


@pytest.mark.parametrize(
    ("check_round", "phase"),
    [
        (1, SessionPhase.PLANNING),
        (2, SessionPhase.PLANNING),
        (3, SessionPhase.CHECK_LOOP_EXHAUSTED),
    ],
)
def test_check_fail_uses_supplied_max_rounds(
    check_round: int, phase: SessionPhase
) -> None:
    assert (
        route_key_insight_check(
            check_output_factory(False),
            check_round=check_round,
            max_check_rounds=3,
        )
        is phase
    )


def test_check_fail_above_supplied_max_rounds_is_rejected() -> None:
    with pytest.raises(InvariantViolationError):
        route_key_insight_check(
            check_output_factory(False), check_round=4, max_check_rounds=3
        )


@pytest.mark.parametrize("check_round", [0, -1, 6])
def test_check_round_out_of_range_is_rejected(check_round: int) -> None:
    with pytest.raises(InvariantViolationError):
        route_key_insight_check(
            check_output_factory(True), check_round=check_round, max_check_rounds=5
        )


@pytest.mark.parametrize(
    ("decision", "phase"),
    [
        ("accept", SessionPhase.AWAITING_WORKING_CONTEXT),
        ("override", SessionPhase.AWAITING_WORKING_CONTEXT),
        ("request_revision", SessionPhase.PLANNING),
    ],
)
def test_each_plan_decision_has_one_route(decision: str, phase: SessionPhase) -> None:
    assert route_plan_decision(decision_factory(decision)) is phase


def test_working_finish_is_not_an_agent_route() -> None:
    with pytest.raises(ValidationError):
        working_output_factory("success")


def test_unknown_working_action_lists_allowed_actions() -> None:
    output = WorkingQAOutput.model_construct(
        action="success",
        reason="处理理由",
        reply="处理回复",
    )
    with pytest.raises(InvariantViolationError, match="report_plan_issue"):
        route_working_output(output)


@pytest.mark.parametrize("action", ["answer", "clarify", "decline"])
def test_non_success_working_actions_stay_working(action: str) -> None:
    assert route_working_output(working_output_factory(action)) is SessionPhase.WORKING


@pytest.mark.parametrize(
    "output",
    [
        idea_output_factory("opinion", "proceed_to_plan"),
        check_output_factory(True),
        decision_factory("override"),
        working_output_factory("answer"),
    ],
)
def test_routing_does_not_mutate_input_models(output) -> None:
    before = output.model_dump(mode="json")
    if isinstance(output, IdeaReviewOutput):
        route_idea_review(output)
    elif isinstance(output, KeyInsightCheckOutput):
        route_key_insight_check(output, check_round=1, max_check_rounds=5)
    elif isinstance(output, UserPlanDecision):
        route_plan_decision(output)
    else:
        route_working_output(output)
    assert output.model_dump(mode="json") == before


def test_routing_has_fixed_public_functions_and_signatures() -> None:
    routing_path = (
        Path(__file__).parents[2] / "src" / "research_mentor" / "harness" / "routing.py"
    )
    module = ast.parse(routing_path.read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    expected = {
        "route_idea_review",
        "route_key_insight_check",
        "route_plan_decision",
        "route_working_output",
        "route_complete",
    }
    assert set(functions) == expected

    def assert_annotation(annotation, expected) -> None:
        assert annotation is expected or annotation == expected.__name__

    idea_signature = inspect.signature(route_idea_review)
    assert list(idea_signature.parameters) == ["output"]
    assert idea_signature.parameters["output"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert idea_signature.parameters["output"].default is inspect.Parameter.empty
    assert_annotation(idea_signature.parameters["output"].annotation, IdeaReviewOutput)
    assert_annotation(idea_signature.return_annotation, SessionPhase)
    assert all(
        parameter.default is inspect.Parameter.empty
        for parameter in idea_signature.parameters.values()
    )

    check_signature = inspect.signature(route_key_insight_check)
    assert list(check_signature.parameters) == [
        "output",
        "check_round",
        "max_check_rounds",
    ]
    assert check_signature.parameters["output"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert check_signature.parameters["output"].default is inspect.Parameter.empty
    assert_annotation(check_signature.parameters["output"].annotation, KeyInsightCheckOutput)
    assert check_signature.parameters["check_round"].kind is inspect.Parameter.KEYWORD_ONLY
    assert check_signature.parameters["max_check_rounds"].kind is inspect.Parameter.KEYWORD_ONLY
    assert check_signature.parameters["check_round"].default is inspect.Parameter.empty
    assert check_signature.parameters["max_check_rounds"].default is inspect.Parameter.empty
    assert_annotation(check_signature.parameters["check_round"].annotation, int)
    assert_annotation(check_signature.parameters["max_check_rounds"].annotation, int)
    assert_annotation(check_signature.return_annotation, SessionPhase)

    plan_signature = inspect.signature(route_plan_decision)
    assert list(plan_signature.parameters) == ["decision"]
    assert plan_signature.parameters["decision"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert plan_signature.parameters["decision"].default is inspect.Parameter.empty
    assert_annotation(plan_signature.parameters["decision"].annotation, UserPlanDecision)
    assert_annotation(plan_signature.return_annotation, SessionPhase)

    working_signature = inspect.signature(route_working_output)
    assert list(working_signature.parameters) == ["output"]
    assert working_signature.parameters["output"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert working_signature.parameters["output"].default is inspect.Parameter.empty
    assert_annotation(working_signature.parameters["output"].annotation, WorkingQAOutput)
    assert_annotation(working_signature.return_annotation, SessionPhase)

    complete_signature = inspect.signature(route_complete)
    assert list(complete_signature.parameters) == ["output"]
    assert complete_signature.parameters["output"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert complete_signature.parameters["output"].default is inspect.Parameter.empty
    assert_annotation(complete_signature.parameters["output"].annotation, CompleteAgentOutput)
    assert_annotation(complete_signature.return_annotation, RoutingDecision)


def test_routing_imports_only_allowed_project_modules() -> None:
    routing_path = (
        Path(__file__).parents[2] / "src" / "research_mentor" / "harness" / "routing.py"
    )
    module = ast.parse(routing_path.read_text(encoding="utf-8"))
    imported_paths = []
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            imported_paths.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            imported_paths.extend(
                f"{module_name}.{alias.name}" for alias in node.names
            )

    forbidden_fragments = (
        "repository",
        "clock",
        "runner",
        "adapters.memory",
        "ports",
        "uuid",
        "datetime",
    )
    assert all(
        not any(fragment in path.lower() for fragment in forbidden_fragments)
        for path in imported_paths
    )
