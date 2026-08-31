from pydantic import ValidationError
import pytest

from research_mentor.config import HarnessConfig
from research_mentor.domain.checks import (
    DimensionScore,
    KeyInsightAssessment,
    KeyInsightDiagnostics,
    KeyInsightScores,
)
from research_mentor.harness.scoring import finalize_key_insight_check
from research_mentor.harness.scoring import score_check


def assessment(**overrides: float) -> KeyInsightAssessment:
    values = {
        "research_fit": 7.0,
        "novelty": 7.0,
        "research_value": 7.0,
        "testability_feasibility": 7.0,
        "evidence_support": 7.0,
    }
    values.update(overrides)
    scores = KeyInsightScores(
        **{
            name: DimensionScore(score=score, reason=f"{name} reason")
            for name, score in values.items()
        }
    )
    return KeyInsightAssessment(
        diagnostics=KeyInsightDiagnostics(
            core_claim="状态压缩提升恢复稳定性",
            expected_contribution="降低长对话状态漂移",
            validation_path="比较恢复正确率",
        ),
        scores=scores,
        reason="总体判断",
        summary_advice="保持验证路径聚焦",
        revision_suggestions=["建议1", "建议2", "建议3", "建议4"],
    )


def test_scoring_passes_when_total_passes() -> None:
    output = finalize_key_insight_check(assessment(), HarnessConfig())

    assert output.final_score == 7.0
    assert output.check_decision is True
    assert output.revision_request == []
    assert output.scoring_rule_version == "v1"


def test_scoring_passes_high_total_even_when_one_dimension_is_low() -> None:
    output = finalize_key_insight_check(
        assessment(evidence_support=2.4),
        HarnessConfig(),
    )

    assert output.final_score == 6.3
    assert output.check_decision is True
    assert output.revision_request == []


def test_harness_score_has_no_dimension_veto() -> None:
    decision = score_check(
        assessment(
            research_fit=8,
            novelty=8,
            research_value=8,
            testability_feasibility=8,
            evidence_support=1,
        ).scores,
        pass_score=6.0,
    )

    assert decision.final_score == 7.0
    assert decision.passed is True


def test_scoring_rejects_total_below_threshold() -> None:
    output = finalize_key_insight_check(
        assessment(
            research_fit=5.0,
            novelty=5.0,
            research_value=5.0,
            testability_feasibility=5.0,
            evidence_support=5.0,
        ),
        HarnessConfig(),
    )

    assert output.final_score == 5.0
    assert output.check_decision is False


def test_output_has_no_dimension_gate_fields() -> None:
    output = finalize_key_insight_check(assessment(), HarnessConfig())

    assert "gate_passed" not in output.__class__.model_fields
    assert "gate_failed_dimensions" not in output.__class__.model_fields


def test_research_fit_and_novelty_use_distinct_declared_weights() -> None:
    output = finalize_key_insight_check(
        assessment(
            research_fit=2.5,
            novelty=10.0,
            research_value=5.0,
            testability_feasibility=5.0,
            evidence_support=5.0,
        ),
        HarnessConfig(),
    )

    assert output.final_score == 5.8


def test_rounded_score_at_pass_threshold_is_accepted() -> None:
    output = finalize_key_insight_check(
        assessment(
            research_fit=5.96,
            novelty=5.96,
            research_value=5.96,
            testability_feasibility=5.96,
            evidence_support=5.96,
        ),
        HarnessConfig(),
    )

    assert output.final_score == 6.0
    assert output.check_decision is True


@pytest.mark.parametrize("score", [-0.1, 10.1])
def test_dimension_score_rejects_score_outside_range(score: float) -> None:
    with pytest.raises(ValidationError):
        DimensionScore(score=score, reason="invalid")


@pytest.mark.parametrize(("score", "expected"), [(5.94, False), (6.0, True)])
def test_total_threshold_is_inclusive(score: float, expected: bool) -> None:
    output = finalize_key_insight_check(
        assessment(
            **dict.fromkeys(
                (
                    "research_fit",
                    "novelty",
                    "research_value",
                    "testability_feasibility",
                    "evidence_support",
                ),
                score,
            )
        ),
        HarnessConfig(),
    )
    assert output.check_decision is expected


def test_default_factories_create_isolated_lists() -> None:
    first = KeyInsightDiagnostics(
        core_claim="a", expected_contribution="b", validation_path="c"
    )
    second = KeyInsightDiagnostics(
        core_claim="a", expected_contribution="b", validation_path="c"
    )
    first.unsupported_claims.append("x")
    assert second.unsupported_claims == []
