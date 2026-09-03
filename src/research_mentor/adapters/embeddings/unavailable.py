"""Explicit unavailable result for missing optional ranker dependencies."""

from collections.abc import Sequence
from pathlib import Path
import importlib.util

from research_mentor.domain.documents import DocumentChunk
from research_mentor.hyperparameters import FLAGEMBEDDING_REPO_URL, RERANKER_MODEL_HUB_URL
from research_mentor.ports.retrieval import RankResult, RetrievalRankerPort


INSTALL_HINT = (
    "FlagEmbedding 未安装。运行: uv sync --extra local-ranking && "
    "uv run --extra local-ranking python -m research_mentor.cli.download_reranker --mirror"
)


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


def optional_flag_embedding_ranker(
    model_name: str,
    *,
    cache_dir: Path | None = None,
) -> RetrievalRankerPort:
    if importlib.util.find_spec("FlagEmbedding") is None:
        return UnavailableRanker(
            f"{INSTALL_HINT} 模型页: {RERANKER_MODEL_HUB_URL} 工具包: {FLAGEMBEDDING_REPO_URL}"
        )
    from research_mentor.adapters.embeddings.flag_embedding import FlagEmbeddingRanker

    return FlagEmbeddingRanker(model_name, cache_dir=cache_dir)
