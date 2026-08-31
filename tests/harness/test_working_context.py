from datetime import datetime, timezone

import pytest

from research_mentor.adapters.embeddings.lexical import LexicalRanker
from research_mentor.adapters.embeddings.unavailable import UnavailableRanker
from research_mentor.agents.working_qa.contracts import CompactContext
from research_mentor.application.context_service import (
    WorkingContextBuilder,
    WorkingContextSource,
)
from research_mentor.config import Settings
from research_mentor.domain.conversations import ConversationTurn
from research_mentor.domain.documents import DocumentChunk
from research_mentor.domain.evidence import EvidenceRef
from research_mentor.domain.experiments import ExperimentInfo, ExperimentTaskContext
from research_mentor.domain.research import KeyInsight, Milestone, ResearchContext, ResearchPlan


def research_context() -> ResearchContext:
    plan = ResearchPlan(
        research_question="缓存策略是否降低尾延迟？",
        knowledge_requirements=[],
        milestones=[Milestone(name="实验", goal="比较延迟", estimated_duration="1天")],
        key_insight=KeyInsight(title="缓存策略", content="比较策略", rationale="可测"),
    )
    return ResearchContext(
        normalized_idea="比较缓存策略对尾延迟的影响",
        research_question=plan.research_question,
        plan=plan,
    )


def current_task() -> ExperimentTaskContext:
    return ExperimentTaskContext(
        task_id="main-1",
        task_kind="main",
        origin="plan",
        status="in_progress",
        experiment_info=ExperimentInfo(
            current_experiment="缓存基准实验",
            actual_result="主实验尾延迟升高 8%",
        ),
    )


def turn(turn_id: str, content: str, minute: int) -> ConversationTurn:
    return ConversationTurn(
        turn_id=turn_id,
        role="user" if minute % 2 else "assistant",
        content=content,
        created_at=datetime(2026, 8, 31, 8, minute, tzinfo=timezone.utc),
    )


def long_source() -> WorkingContextSource:
    return WorkingContextSource(
        research_context=research_context(),
        current_task=current_task(),
        conversation_turns=[
            turn("t1", "早期实验设置\n" + "x" * 12000, 1),
            turn("t2", "观察到延迟变化\n" + "y" * 12000, 2),
            turn("t3", "是否为数据倾斜导致？", 3),
            turn("t4", "请分析当前结果", 4),
        ],
        document_chunks=[
            DocumentChunk(
                chunk_id="chunk-1",
                document_id="doc-1",
                ordinal=0,
                heading_path=["结果"],
                markdown="缓存实验显示 tail latency 升高",
            )
        ],
        evidence_refs=[
            EvidenceRef(
                title="已有实验说明",
                source_type="other",
                support="说明测量口径",
            )
        ],
        facts=["主实验尾延迟升高 8%"],
        unresolved_questions=["是否为数据倾斜导致？"],
    )


@pytest.mark.asyncio
async def test_working_context_keeps_current_task_and_recent_results() -> None:
    builder = WorkingContextBuilder(Settings(), LexicalRanker())

    context = await builder.build(
        long_source(), "为什么延迟升高？", character_budget=12000
    )

    assert context.current_task.task_id == long_source().current_task.task_id
    assert context.compact_context is not None
    assert context.compact_context.source_turn_ids
    assert all(ref.source_id for ref in context.evidence_refs)
    assert [item.turn_id for item in context.recent_turns] == ["t3", "t4"]


@pytest.mark.asyncio
async def test_compaction_preserves_facts_and_unresolved_questions() -> None:
    builder = WorkingContextBuilder(Settings(), LexicalRanker())

    context = await builder.build(
        long_source(), "下一步是什么？", character_budget=12000
    )

    assert context.compact_context == CompactContext(
        summary="早期实验设置；观察到延迟变化",
        source_turn_ids=["t1", "t2"],
        facts=["主实验尾延迟升高 8%"],
        unresolved_questions=["是否为数据倾斜导致？"],
    )


@pytest.mark.asyncio
async def test_rank_unavailable_does_not_decline_question() -> None:
    builder = WorkingContextBuilder(Settings(), UnavailableRanker("model_missing"))

    context = await builder.build(
        long_source(), "比较另一种缓存策略", character_budget=12000
    )

    assert context.rank_status == "unavailable"
    assert context.retrieval_diagnostics[0].limitation == "model_missing"
    assert context.decline_as_unrelated is False


@pytest.mark.asyncio
async def test_successful_low_rank_uses_configured_threshold() -> None:
    settings = Settings(rag_relevance_threshold=0.3)
    builder = WorkingContextBuilder(settings, LexicalRanker())

    context = await builder.build(
        long_source(), "明天的天气？", character_budget=12000
    )

    assert context.rank_status == "ok"
    assert context.top_relevance == 0.0
    assert context.decline_as_unrelated is True


@pytest.mark.asyncio
async def test_same_input_has_stable_summary_and_budget_boundary() -> None:
    builder = WorkingContextBuilder(Settings(), LexicalRanker())
    first = await builder.build(long_source(), "下一步是什么？", character_budget=12000)
    second = await builder.build(long_source(), "下一步是什么？", character_budget=12000)

    assert first == second
    assert sum(len(item.content) for item in first.recent_turns) < 12000
