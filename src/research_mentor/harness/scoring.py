from research_mentor.config import HarnessConfig
from research_mentor.domain.checks import (
    CheckDecision,
    KeyInsightAssessment,
    KeyInsightCheckOutput,
    KeyInsightScores,
)

SCORE_WEIGHTS = {
    "research_fit": 0.20,
    "novelty": 0.25,
    "research_value": 0.20,
    "testability_feasibility": 0.20,
    "evidence_support": 0.15,
}


def score_check(scores: KeyInsightScores, pass_score: float) -> CheckDecision:
    final_score = round(
        0.20 * scores.research_fit.score
        + 0.25 * scores.novelty.score
        + 0.20 * scores.research_value.score
        + 0.20 * scores.testability_feasibility.score
        + 0.15 * scores.evidence_support.score,
        1,
    )
    return CheckDecision(
        final_score=final_score,
        passed=final_score >= pass_score,
    )


def finalize_key_insight_check(
    assessment: KeyInsightAssessment,
    config: HarnessConfig,
) -> KeyInsightCheckOutput:
    decision = score_check(assessment.scores, config.pass_score)
    if decision.passed:
        decision_reason = "加权总分达到通过阈值。"
        revision_request: list[str] = []
    else:
        decision_reason = "加权总分未达到通过阈值。"
        revision_request = assessment.revision_suggestions[:3]
    return KeyInsightCheckOutput(
        assessment=assessment,
        final_score=decision.final_score,
        check_decision=decision.passed,
        decision_reason=decision_reason,
        revision_request=revision_request,
        scoring_rule_version=config.scoring_rule_version,
    )
