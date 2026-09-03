"""Choose the Working document ranker without loading weights in tests."""

from __future__ import annotations

import os

from research_mentor.adapters.embeddings.huggingface_hub_env import (
    configure_huggingface_hub,
)
from research_mentor.adapters.embeddings.lexical import LexicalRanker
from research_mentor.adapters.embeddings.unavailable import (
    UnavailableRanker,
    optional_flag_embedding_ranker,
)
from research_mentor.config import Settings
from research_mentor.ports.retrieval import RetrievalRankerPort


def document_ranker_for(settings: Settings) -> RetrievalRankerPort:
    configure_huggingface_hub(
        endpoint=settings.hf_endpoint,
        token=settings.huggingface_hub_token(),
    )
    if settings.reranker_backend == "lexical":
        return LexicalRanker()
    if settings.reranker_backend == "unavailable":
        return UnavailableRanker("reranker disabled")
    if os.environ.get("PYTEST_VERSION") and settings.reranker_backend == "auto":
        return UnavailableRanker("pytest skips FlagEmbedding weights")
    return optional_flag_embedding_ranker(
        settings.reranker_model,
        cache_dir=settings.reranker_cache_dir,
    )
