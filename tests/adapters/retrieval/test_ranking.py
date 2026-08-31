import importlib.util

from research_mentor.adapters.embeddings.lexical import LexicalRanker
from research_mentor.adapters.embeddings.flag_embedding import FlagEmbeddingRanker
from research_mentor.adapters.embeddings.unavailable import (
    UnavailableRanker,
    optional_flag_embedding_ranker,
)
from research_mentor.domain.documents import DocumentChunk
from research_mentor.ports.retrieval import RetrievalRankerPort


CHUNKS = [
    DocumentChunk(
        chunk_id="c1",
        document_id="d1",
        ordinal=0,
        heading_path=["方法"],
        markdown="缓存一致性实验",
    ),
    DocumentChunk(
        chunk_id="c2",
        document_id="d1",
        ordinal=1,
        heading_path=["结果"],
        markdown="缓存策略降低延迟",
    ),
    DocumentChunk(
        chunk_id="c3",
        document_id="d1",
        ordinal=2,
        heading_path=["背景"],
        markdown="无关内容",
    ),
]


def test_lexical_ranker_is_deterministic() -> None:
    ranked = LexicalRanker().rank("缓存 延迟", CHUNKS, limit=2)

    assert [item.chunk.chunk_id for item in ranked.items] == ["c2", "c1"]
    assert all(0.0 <= item.score <= 1.0 for item in ranked.items)
    assert ranked.status == "ok"


def test_real_mode_uses_unavailable_ranker_without_optional_dependency(
    monkeypatch,
) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda _: None)

    ranker = optional_flag_embedding_ranker("BAAI/bge-reranker-v2-m3")
    result = ranker.rank("x", CHUNKS, limit=2)

    assert isinstance(ranker, UnavailableRanker)
    assert result.status == "unavailable"
    assert result.items == []
    assert result.limitation == "FlagEmbedding 未安装"


def test_ranker_port_has_one_result_contract() -> None:
    assert isinstance(LexicalRanker(), RetrievalRankerPort)


def test_lexical_ranker_does_not_mutate_or_return_more_than_limit() -> None:
    before = [chunk.model_dump(mode="json") for chunk in CHUNKS]

    result = LexicalRanker().rank("缓存", CHUNKS, limit=1)

    assert len(result.items) == 1
    assert [chunk.model_dump(mode="json") for chunk in CHUNKS] == before


def test_flag_embedding_adapter_uses_same_rank_result_contract() -> None:
    class FakeModel:
        def compute_score(self, pairs, normalize):
            assert normalize is True
            assert len(pairs) == len(CHUNKS)
            return [0.2, 0.9, 0.1]

    result = FlagEmbeddingRanker("unused", model=FakeModel()).rank(
        "缓存 延迟",
        CHUNKS,
        limit=2,
    )

    assert [item.chunk.chunk_id for item in result.items] == ["c2", "c1"]
    assert [item.score for item in result.items] == [0.9, 0.2]
