from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.application.views import _visible_evidence
from research_mentor.domain.checks import (
    DimensionScore,
    KeyInsightAssessment,
    KeyInsightCheckOutput,
    KeyInsightDiagnostics,
    KeyInsightScores,
)
from research_mentor.domain.evidence import EvidenceRef, LiteratureRecord
from research_mentor.harness.state import ResearchSession
from research_mentor.hyperparameters import SCORING_RULE_VERSION


def test_visible_evidence_distinguishes_retrieved_and_adopted() -> None:
    retrieved = LiteratureRecord(
        title="Retrieved only",
        source_type="paper",
        url="https://example.com/a",
        summary="未采用摘要",
        relevance="相关检索",
        record_id="r1",
    )
    adopted = LiteratureRecord(
        title="Adopted paper",
        source_type="paper",
        url="https://example.com/b",
        summary="采用摘要",
        relevance="支撑主张",
        record_id="r2",
    )
    review = IdeaReviewOutput(
        idea_type="opinion",
        action="proceed_to_plan",
        normalized_idea="评估状态压缩",
        reason="可验证",
        next_action="制定方案",
        literature_searches=[retrieved, adopted],
        evidence=[
            EvidenceRef(
                title="Adopted paper",
                source_type="paper",
                url="https://example.com/b",
                support="支撑核心主张",
            )
        ],
    )
    session = ResearchSession(session_id="s1", idea_review=review)

    items = _visible_evidence(session, [])
    by_title = {item.title: item.selected for item in items}

    assert by_title["Retrieved only"] is False
    assert by_title["Adopted paper"] is True


def test_visible_evidence_marks_check_citations_as_adopted() -> None:
    literature = LiteratureRecord(
        title="Check citation",
        source_type="paper",
        url="https://example.com/c",
        summary="检索到",
        relevance="候选",
        record_id="r3",
    )
    scores = KeyInsightScores(
        **{
            name: DimensionScore(score=7.0, reason="ok")
            for name in (
                "research_fit",
                "novelty",
                "research_value",
                "testability_feasibility",
                "evidence_support",
            )
        }
    )
    session = ResearchSession(
        session_id="s1",
        latest_check=KeyInsightCheckOutput(
            assessment=KeyInsightAssessment(
                diagnostics=KeyInsightDiagnostics(
                    core_claim="主张",
                    expected_contribution="贡献",
                    validation_path="验证",
                ),
                scores=scores,
                reason="判断",
                evidence=[
                    EvidenceRef(
                        title="Check citation",
                        source_type="paper",
                        url="https://example.com/c",
                        support="用于评分",
                    )
                ],
                summary_advice="建议",
            ),
            final_score=7.0,
            check_decision=True,
            decision_reason="通过",
            scoring_rule_version=SCORING_RULE_VERSION,
        ),
    )

    items = _visible_evidence(session, [literature])

    assert items[0].title == "Check citation"
    assert items[0].selected is True
