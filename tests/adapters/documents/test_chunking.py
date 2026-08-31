from research_mentor.adapters.documents.chunking import MarkdownChunker


def test_chunker_returns_normative_document_chunks() -> None:
    chunks = MarkdownChunker(max_chars=12, overlap_chars=3).split(
        "d1",
        "# 方法\n第一段内容。\n\n第二段内容。",
    )

    assert chunks[0].chunk_id
    assert chunks[0].ordinal == 0
    assert chunks[0].heading_path == ["方法"]
    assert chunks[0].markdown
    assert all(len(chunk.markdown) <= 12 for chunk in chunks)


def test_chunk_ids_and_boundaries_are_deterministic() -> None:
    chunker = MarkdownChunker(max_chars=10, overlap_chars=2)
    markdown = "# 结果\n这是一个超过限制的较长段落。"

    first = chunker.split("d1", markdown)
    second = chunker.split("d1", markdown)

    assert first == second
    assert [chunk.ordinal for chunk in first] == list(range(len(first)))
    assert all(chunk.heading_path == ["结果"] for chunk in first)


def test_empty_document_has_no_chunks() -> None:
    assert MarkdownChunker(max_chars=12, overlap_chars=3).split("d1", "") == []
