"""Deterministic Working QA context selection and compaction."""

import asyncio
from collections.abc import Sequence

from pydantic import BaseModel, Field

from research_mentor.agents.working_qa.contracts import CompactContext, WorkingContext
from research_mentor.config import Settings
from research_mentor.domain.conversations import ConversationTurn
from research_mentor.domain.documents import DocumentChunk
from research_mentor.domain.evidence import EvidenceRef, RetrievalDiagnostics
from research_mentor.domain.experiments import ExperimentTaskContext
from research_mentor.domain.research import ResearchContext
from research_mentor.ports.retrieval import RetrievalRankerPort


class WorkingContextSource(BaseModel):
    research_context: ResearchContext
    current_task: ExperimentTaskContext
    conversation_turns: list[ConversationTurn] = Field(default_factory=list)
    document_chunks: list[DocumentChunk] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    retrieval_diagnostics: list[RetrievalDiagnostics] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)


class WorkingContextBuilder:
    def __init__(self, settings: Settings, ranker: RetrievalRankerPort) -> None:
        self.settings = settings
        self._ranker = ranker

    async def build(
        self,
        source: WorkingContextSource,
        question: str,
        *,
        character_budget: int | None = None,
    ) -> WorkingContext:
        budget = (
            self.settings.working_context_character_budget
            if character_budget is None
            else character_budget
        )
        if budget < 1:
            raise ValueError("character_budget must be positive")
        rank_result = await asyncio.to_thread(
            self._ranker.rank,
            question,
            source.document_chunks,
            limit=10,
        )
        ranked_evidence = [
            EvidenceRef(
                source_id=item.chunk.chunk_id,
                title=(
                    item.chunk.heading_path[-1]
                    if item.chunk.heading_path
                    else item.chunk.document_id
                ),
                source_type="other",
                support="项目文档片段与当前问题相关",
            )
            for item in rank_result.items
        ]
        evidence_refs = [
            item.model_copy(
                deep=True,
                update={
                    "source_id": item.source_id
                    or (f"doi:{item.doi}" if item.doi else None)
                    or (f"url:{item.url}" if item.url else None)
                    or f"title:{item.title}"
                },
            )
            for item in [*source.evidence_refs, *ranked_evidence]
        ]
        top_relevance = (
            max(item.score for item in rank_result.items)
            if rank_result.items
            else None
        )
        decline_as_unrelated = (
            rank_result.status == "ok"
            and top_relevance is not None
            and top_relevance < self.settings.rag_relevance_threshold
        )
        diagnostics = [
            item.model_copy(deep=True) for item in source.retrieval_diagnostics
        ]
        if rank_result.status == "unavailable":
            diagnostics.append(
                RetrievalDiagnostics(
                    query=question,
                    provider="project_ranker",
                    candidate_count=len(source.document_chunks),
                    selected_count=0,
                    status="unavailable",
                    limitation=rank_result.limitation,
                )
            )
        else:
            diagnostics.append(
                RetrievalDiagnostics(
                    query=question,
                    provider="project_ranker",
                    candidate_count=len(source.document_chunks),
                    selected_count=len(rank_result.items),
                    top_relevance=top_relevance,
                    status="ok" if rank_result.items else "empty",
                )
            )

        recent_turns, compact_context = self._select_turns(
            source,
            question,
            evidence_refs,
            budget,
        )
        return WorkingContext(
            research_context=source.research_context.model_copy(deep=True),
            current_task=source.current_task.model_copy(deep=True),
            recent_turns=recent_turns,
            compact_context=compact_context,
            evidence_refs=evidence_refs,
            retrieval_diagnostics=diagnostics,
            rank_status=rank_result.status,
            top_relevance=top_relevance,
            decline_as_unrelated=decline_as_unrelated,
        )

    @staticmethod
    def _select_turns(
        source: WorkingContextSource,
        question: str,
        evidence_refs: Sequence[EvidenceRef],
        budget: int,
    ) -> tuple[list[ConversationTurn], CompactContext | None]:
        fixed_size = sum(
            [
                len(source.research_context.model_dump_json()),
                len(source.current_task.model_dump_json()),
                len(question),
                *(len(item) for item in source.facts),
                *(len(item) for item in source.unresolved_questions),
                *(len(item.model_dump_json()) for item in evidence_refs),
            ]
        )
        remaining = max(0, budget - fixed_size)
        ordered = sorted(
            source.conversation_turns,
            key=lambda item: (item.created_at, item.turn_id),
        )
        recent_reversed: list[ConversationTurn] = []
        used = 0
        for item in reversed(ordered):
            size = len(item.content)
            if used + size <= remaining:
                recent_reversed.append(item.model_copy(deep=True))
                used += size
        recent_ids = {item.turn_id for item in recent_reversed}
        compacted = [item for item in ordered if item.turn_id not in recent_ids]
        compact_context = None
        if compacted or source.facts or source.unresolved_questions:
            summary_parts = [
                item.content.splitlines()[0].strip()
                for item in compacted
                if item.content.splitlines()[0].strip()
            ]
            compact_context = CompactContext(
                summary="；".join(summary_parts)[: min(2000, budget // 4)],
                source_turn_ids=[item.turn_id for item in compacted],
                facts=list(source.facts),
                unresolved_questions=list(source.unresolved_questions),
            )
        return list(reversed(recent_reversed)), compact_context
