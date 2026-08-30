import json
from pathlib import Path

import pytest

from research_mentor.config import HarnessConfig
from research_mentor.domain.checks import (
    DimensionScore,
    KeyInsightAssessment,
    KeyInsightDiagnostics,
    KeyInsightScores,
)
from research_mentor.harness.scoring import finalize_key_insight_check


CASES_PATH = (
    Path(__file__).resolve().parents[2]
    / "evals"
    / "key_insight_check_cases.json"
)


def load_cases() -> list[dict[str, object]]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", load_cases(), ids=lambda case: case["id"])
def test_key_insight_check_scoring_eval(case: dict[str, object]) -> None:
    scores = case["scores"]
    assessment = KeyInsightAssessment(
        diagnostics=KeyInsightDiagnostics(
            core_claim=str(case["key_insight_summary"]),
            expected_contribution="验证评分决策",
            validation_path="运行确定性评分回归",
        ),
        scores=KeyInsightScores(
            **{
                name: DimensionScore(score=value, reason="Eval 固定评分")
                for name, value in scores.items()
            }
        ),
        reason=str(case["description"]),
        summary_advice="依据总分决定是否修改",
        revision_suggestions=["聚焦最低分维度并补充可验证依据"],
    )

    output = finalize_key_insight_check(assessment, HarnessConfig())

    assert output.final_score == case["expected_final_score"]
    assert output.check_decision is case["expected_check_decision"]
    assert output.revision_request == (
        []
        if case["expected_check_decision"]
        else assessment.revision_suggestions
    )
