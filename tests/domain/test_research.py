import pytest
from pydantic import ValidationError

from research_mentor.domain.evidence import EvidenceRef, LiteratureRecord
from research_mentor.domain.research import (
    InitialInput,
    KeyInsight,
    KnowledgeItem,
    Milestone,
    OverrideRecord,
    ResearchPlan,
    UserPlanDecision,
)


def insight(title: str = "可验证增量") -> KeyInsight:
    return KeyInsight(
        title=title,
        content="比较状态压缩前后的恢复正确率",
        rationale="直接检验长期状态保持能力",
    )


@pytest.mark.parametrize("value", ["", "   "])
def test_initial_input_rejects_blank_idea(value: str) -> None:
    with pytest.raises(ValidationError):
        InitialInput(original_idea=value, domain="computer science")


def test_initial_input_rejects_more_than_19999_characters() -> None:
    with pytest.raises(ValidationError):
        InitialInput(original_idea="x" * 20000, domain="computer science")


@pytest.mark.parametrize("length", [1, 19999])
def test_initial_input_accepts_idea_length_boundaries(length: int) -> None:
    value = InitialInput(original_idea="x" * length, domain="computer science")
    assert len(value.original_idea) == length


def test_initial_input_accepts_complete_input() -> None:
    value = InitialInput(
        original_idea="研究 Agent memory",
        domain="computer science",
        time_limit="两周",
        available_resources=["GPU"],
        unavailable_resources=["商业 API"],
        other_constraints=["需要可复现实验"],
    )
    assert value.available_resources == ["GPU"]


@pytest.mark.parametrize("value", ["", "\t"])
def test_initial_input_rejects_blank_domain(value: str) -> None:
    with pytest.raises(ValidationError):
        InitialInput(original_idea="研究 Agent memory", domain=value)


def test_request_revision_requires_reason() -> None:
    with pytest.raises(ValidationError):
        UserPlanDecision(decision="request_revision")


def test_request_revision_rejects_whitespace_reason() -> None:
    with pytest.raises(ValidationError):
        UserPlanDecision(decision="request_revision", user_reason=" \t ")


def test_request_revision_rejects_override_payload() -> None:
    with pytest.raises(ValidationError):
        UserPlanDecision(
            decision="request_revision",
            user_reason="请补充消融实验",
            overridden_key_insight=insight(),
        )


def test_override_requires_user_key_insight() -> None:
    with pytest.raises(ValidationError):
        UserPlanDecision(decision="override", user_reason="坚持该路线")


def test_accept_rejects_override_payload() -> None:
    with pytest.raises(ValidationError):
        UserPlanDecision(decision="accept", overridden_key_insight=insight())


def test_override_accepts_explicit_user_choice() -> None:
    decision = UserPlanDecision(
        decision="override",
        user_reason="现有资源只支持该方法",
        overridden_key_insight=insight("用户路线"),
    )
    assert decision.overridden_key_insight is not None
    assert decision.overridden_key_insight.title == "用户路线"


def test_evidence_models_accept_representative_values_and_isolate_lists() -> None:
    literature = LiteratureRecord(
        title="Agent Memory",
        source_type="paper",
        summary="memory methods",
        relevance="direct",
    )
    reference = EvidenceRef(title="Agent Memory", source_type="paper", support="supports claim")
    assert literature.title == reference.title
    first = LiteratureRecord(
        title="A", source_type="book", summary="s", relevance="r"
    )
    second = LiteratureRecord(
        title="B", source_type="book", summary="s", relevance="r"
    )
    first.authors.append("Author")
    assert second.authors == []


def test_research_plan_and_override_record_accept_representative_values() -> None:
    key_insight = insight()
    plan = ResearchPlan(
        research_question="压缩是否保持记忆效果？",
        knowledge_requirements=[KnowledgeItem(topic="压缩", reason="确定机制")],
        milestones=[Milestone(name="基线", goal="建立基线", estimated_duration="2 days")],
        key_insight=key_insight,
    )
    record = OverrideRecord(
        agent_recommendation=key_insight,
        user_choice=insight("用户路线"),
        agent_reason="资源约束",
        timestamp="2026-08-29T00:00:00Z",
    )
    assert plan.key_insight.title == record.agent_recommendation.title
    assert plan.open_issues == []
    assert record.user_reason is None


def test_research_list_defaults_are_not_shared() -> None:
    first = KeyInsight(title="A", content="c", rationale="r")
    second = KeyInsight(title="B", content="c", rationale="r")
    first.evidence.append(EvidenceRef(title="E", source_type="other", support="s"))
    assert second.evidence == []
