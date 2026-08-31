"""Optional FlagEmbedding reranker adapter."""

from collections.abc import Sequence
import math
from typing import Any

from research_mentor.domain.documents import DocumentChunk
from research_mentor.ports.retrieval import RankedChunk, RankResult


class FlagEmbeddingRanker:
    def __init__(self, model_name: str, *, model: Any | None = None) -> None:
        if model is None:
            from FlagEmbedding import FlagReranker

            model = FlagReranker(model_name, use_fp16=True)
        self._model = model

    def rank(
        self,
        query: str,
        chunks: Sequence[DocumentChunk],
        *,
        limit: int,
    ) -> RankResult:
        if limit <= 0 or not chunks:
            return RankResult(status="ok")
        pairs = [
            [query, "\n".join([*chunk.heading_path, chunk.markdown])]
            for chunk in chunks
        ]
        raw_scores = self._model.compute_score(pairs, normalize=True)
        if isinstance(raw_scores, (int, float)):
            raw_scores = [raw_scores]
        ranked = sorted(
            zip(raw_scores, chunks, strict=True),
            key=lambda item: (-float(item[0]), item[1].chunk_id),
        )
        return RankResult(
            status="ok",
            items=[
                RankedChunk(
                    chunk=chunk.model_copy(deep=True),
                    score=self._normalize(float(score)),
                )
                for score, chunk in ranked[:limit]
            ],
        )

    @staticmethod
    def _normalize(score: float) -> float:
        if 0.0 <= score <= 1.0:
            return score
        return 1.0 / (1.0 + math.exp(-score))
