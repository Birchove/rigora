"""Deterministic lexical ranker for demo and tests."""

from collections.abc import Sequence

from research_mentor.domain.documents import DocumentChunk
from research_mentor.ports.retrieval import RankedChunk, RankResult


class LexicalRanker:
    def rank(
        self,
        query: str,
        chunks: Sequence[DocumentChunk],
        *,
        limit: int,
    ) -> RankResult:
        if limit <= 0:
            return RankResult(status="ok")
        terms = tuple(dict.fromkeys(query.lower().split()))
        scored = [
            (
                self._score(terms, chunk),
                chunk,
            )
            for chunk in chunks
        ]
        scored.sort(key=lambda item: (-item[0], item[1].chunk_id))
        return RankResult(
            status="ok",
            items=[
                RankedChunk(
                    chunk=chunk.model_copy(deep=True),
                    score=score,
                )
                for score, chunk in scored[:limit]
            ],
        )

    @staticmethod
    def _score(terms: tuple[str, ...], chunk: DocumentChunk) -> float:
        if not terms:
            return 0.0
        content = " ".join([*chunk.heading_path, chunk.markdown]).lower()
        return sum(term in content for term in terms) / len(terms)
