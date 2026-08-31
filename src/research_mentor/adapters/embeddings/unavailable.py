"""Explicit unavailable result for missing optional ranker dependencies."""

from collections.abc import Sequence
import importlib.util

from research_mentor.domain.documents import DocumentChunk
from research_mentor.ports.retrieval import RankResult, RetrievalRankerPort


class UnavailableRanker:
    def __init__(self, limitation: str) -> None:
        self._limitation = limitation

    def rank(
        self,
        query: str,
        chunks: Sequence[DocumentChunk],
        *,
        limit: int,
    ) -> RankResult:
        return RankResult(
            status="unavailable",
            limitation=self._limitation,
        )


def optional_flag_embedding_ranker(model_name: str) -> RetrievalRankerPort:
    if importlib.util.find_spec("FlagEmbedding") is None:
        return UnavailableRanker("FlagEmbedding 未安装")
    from research_mentor.adapters.embeddings.flag_embedding import (
        FlagEmbeddingRanker,
    )

    return FlagEmbeddingRanker(model_name)
