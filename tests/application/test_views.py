from datetime import datetime, timezone

from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.application.views import _visible_evidence, _working_turns
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
from research_mentor.ports.events import PersistedPublicEvent


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


def test_working_turns_expose_validated_reply() -> None:
    occurred = datetime(2026, 9, 3, tzinfo=timezone.utc)
    events = [
        PersistedPublicEvent(
            project_id="p1",
            sequence=6,
            event_type="plan_decided",
            topic="agent.stage",
            phase_before="awaiting_plan_decision",
            phase_after="working",
            payload={"decision": "accept"},
            occurred_at=occurred,
        ),
        PersistedPublicEvent(
            project_id="p1",
            sequence=7,
            event_type="working_turn_completed",
            topic="agent.stage",
            phase_before="working",
            phase_after="working",
            payload={
                "action": "answer",
                "reason": "信息足够",
                "reply": "先固定随机种子再比较显存。",
                "question": "主实验第一步怎么卡死变量？",
            },
            occurred_at=occurred,
        ),
        PersistedPublicEvent(
            project_id="p1",
            sequence=8,
            event_type="working_turn_completed",
            topic="agent.stage",
            phase_before="working",
            phase_after="working",
            payload={"action": "answer", "reason": "空回复", "reply": "   "},
            occurred_at=occurred,
        ),
    ]

    turns = _working_turns(events)

    assert len(turns) == 1
    assert turns[0].action == "answer"
    assert turns[0].reply == "先固定随机种子再比较显存。"
    assert turns[0].reason == "信息足够"
    assert turns[0].question == "主实验第一步怎么卡死变量？"
