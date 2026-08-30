from research_mentor.config import HarnessConfig
from research_mentor.domain.checks import (
    KeyInsightAssessment,
    KeyInsightCheckOutput,
)

SCORE_WEIGHTS = {
    "research_fit": 0.20,
    "novelty": 0.25,
    "research_value": 0.20,
    "testability_feasibility": 0.20,
    "evidence_support": 0.15,
}


def finalize_key_insight_check(
    assessment: KeyInsightAssessment,
    config: HarnessConfig,
) -> KeyInsightCheckOutput:
    raw_scores = {
        name: getattr(assessment.scores, name).score
        for name in SCORE_WEIGHTS
    }
    final_score = round(
        sum(raw_scores[name] * weight for name, weight in SCORE_WEIGHTS.items()),
        1,
    )
    decision = final_score >= config.pass_score
    if decision:
        decision_reason = "加权总分达到通过阈值。"
        revision_request: list[str] = []
    else:
        decision_reason = "加权总分未达到通过阈值。"
        revision_request = assessment.revision_suggestions[:3]
    return KeyInsightCheckOutput(
        assessment=assessment,
        final_score=final_score,
        check_decision=decision,
        decision_reason=decision_reason,
        revision_request=revision_request,
        scoring_rule_version=config.scoring_rule_version,
    )
