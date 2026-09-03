"""Optional FlagEmbedding reranker adapter."""

from collections.abc import Sequence
from pathlib import Path
import math
import os
from typing import Any

from research_mentor.domain.documents import DocumentChunk
from research_mentor.ports.retrieval import RankedChunk, RankResult


def local_reranker_dir(model_name: str, cache_dir: Path) -> Path:
    return cache_dir / model_name.replace("/", "--")


class FlagEmbeddingRanker:
    def __init__(
        self,
        model_name: str,
        *,
        model: Any | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self._model_name = model_name
        self._cache_dir = Path(cache_dir) if cache_dir is not None else None
        self._model = model
        self._load_error: str | None = None

    def model_path(self) -> str:
        if self._cache_dir is not None:
            local = local_reranker_dir(self._model_name, self._cache_dir)
            if (local / "config.json").is_file():
                return str(local)
        return self._model_name

    def rank(
        self,
        query: str,
        chunks: Sequence[DocumentChunk],
        *,
        limit: int,
    ) -> RankResult:
        if limit <= 0 or not chunks:
            return RankResult(status="ok")
        model = self._ensure_model()
        if model is None:
            return RankResult(
                status="unavailable",
                limitation=self._load_error or "FlagEmbedding 不可用",
            )
        pairs = [
            [query, "\n".join([*chunk.heading_path, chunk.markdown])]
            for chunk in chunks
        ]
        raw_scores = model.compute_score(pairs, normalize=True)
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

    def _ensure_model(self) -> Any | None:
        if self._model is not None or self._load_error is not None:
            return self._model
        try:
            if self._cache_dir is not None:
                self._cache_dir.mkdir(parents=True, exist_ok=True)
                os.environ.setdefault("HF_HOME", str(self._cache_dir.resolve()))
            from FlagEmbedding import FlagReranker

            path = self.model_path()
            try:
                self._model = FlagReranker(path, use_fp16=True)
            except Exception:
                self._model = FlagReranker(path, use_fp16=False)
        except Exception as exc:
            self._load_error = f"FlagEmbedding 权重不可用: {exc}"
            self._model = None
        return self._model

    @staticmethod
    def _normalize(score: float) -> float:
        if 0.0 <= score <= 1.0:
            return score
        return 1.0 / (1.0 + math.exp(-score))
