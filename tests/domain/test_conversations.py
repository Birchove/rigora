from datetime import UTC, datetime

from research_mentor.domain.conversations import ConversationTurn


NOW = datetime(2026, 8, 31, tzinfo=UTC)


def test_conversation_turn_preserves_provenance() -> None:
    turn = ConversationTurn(
        turn_id="t1",
        role="assistant",
        content="结论",
        created_at=NOW,
        agent_name="working_qa",
        evidence_ids=["e1"],
    )

    assert turn.evidence_ids == ["e1"]


def test_conversation_turn_evidence_defaults_are_not_shared() -> None:
    first = ConversationTurn(
        turn_id="t1", role="user", content="问题一", created_at=NOW
    )
    second = ConversationTurn(
        turn_id="t2", role="user", content="问题二", created_at=NOW
    )

    first.evidence_ids.append("e1")

    assert second.evidence_ids == []
