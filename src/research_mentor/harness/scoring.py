from collections.abc import Mapping

from research_mentor.config import HarnessConfig
from research_mentor.domain.checks import (
    CheckDecision,
    KeyInsightAssessment,
    KeyInsightCheckOutput,
    KeyInsightScores,
)
from research_mentor.hyperparameters import (
    CHECK_DIMENSION_FLOORS,
    CHECK_REVISION_REQUEST_LIMIT,
    SCORE_WEIGHTS,
)


def score_check(
    scores: KeyInsightScores,
    pass_score: float,
    dimension_floors: Mapping[str, float] | None = None,
) -> CheckDecision:
    floors = dict(dimension_floors) if dimension_floors is not None else dict(
        CHECK_DIMENSION_FLOORS
    )
    final_score = round(
        sum(
            SCORE_WEIGHTS[name] * getattr(scores, name).score
            for name in SCORE_WEIGHTS
        ),
        1,
    )
    failed_dimensions = [
        name
        for name, floor in floors.items()
        if getattr(scores, name).score < floor
    ]
    return CheckDecision(
        final_score=final_score,
        passed=final_score >= pass_score and not failed_dimensions,
        failed_dimensions=failed_dimensions,
    )


def finalize_key_insight_check(
    assessment: KeyInsightAssessment,
    config: HarnessConfig,
) -> KeyInsightCheckOutput:
    decision = score_check(
        assessment.scores,
        config.pass_score,
        config.dimension_floors,
    )
    if decision.passed:
        decision_reason = "加权总分达到通过阈值，且各维不低于下界。"
        revision_request: list[str] = []
    elif decision.failed_dimensions:
        names = "、".join(decision.failed_dimensions)
        if decision.final_score < config.pass_score:
            decision_reason = f"加权总分未达到通过阈值，且单项低于下界：{names}。"
        else:
            decision_reason = f"单项低于下界：{names}。"
        revision_request = assessment.revision_suggestions[:CHECK_REVISION_REQUEST_LIMIT]
    else:
        decision_reason = "加权总分未达到通过阈值。"
        revision_request = assessment.revision_suggestions[:CHECK_REVISION_REQUEST_LIMIT]
    return KeyInsightCheckOutput(
        assessment=assessment,
        final_score=decision.final_score,
        check_decision=decision.passed,
        decision_reason=decision_reason,
        revision_request=revision_request,
        scoring_rule_version=config.scoring_rule_version,
    )
