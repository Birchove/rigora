from collections.abc import AsyncIterator
import threading

import pytest

from research_mentor.adapters.documents.anydoc import AnydocParser
from research_mentor.adapters.documents.plain_text import PlainTextParser
from research_mentor.adapters.filestore.local import LocalFileStore
from research_mentor.errors import DocumentParseFailed


async def bytes_stream(content: bytes) -> AsyncIterator[bytes]:
    yield content


@pytest.mark.asyncio
@pytest.mark.parametrize("media_type", ["text/plain", "text/markdown"])
async def test_plain_text_parser_returns_normalized_markdown(
    tmp_path,
    media_type: str,
) -> None:
    stored = await LocalFileStore(tmp_path).put(
        "p1", "d1", bytes_stream("# 标题\r\n正文".encode())
    )

    parsed = await PlainTextParser().parse(stored, media_type)

    assert parsed.markdown == "# 标题\n正文"
    assert parsed.parser_metadata == {"parser": "plain_text"}


@pytest.mark.asyncio
async def test_plain_text_parser_rejects_invalid_utf8(tmp_path) -> None:
    stored = await LocalFileStore(tmp_path).put("p1", "d1", bytes_stream(b"\xff"))

    with pytest.raises(DocumentParseFailed):
        await PlainTextParser().parse(stored, "text/plain")


@pytest.mark.asyncio
async def test_anydoc_runs_converter_off_the_event_loop_thread(tmp_path) -> None:
    stored = await LocalFileStore(tmp_path).put("p1", "d1", bytes_stream(b"document"))
    event_loop_thread = threading.get_ident()
    converter_thread: int | None = None

    def converter(path) -> str:
        nonlocal converter_thread
        converter_thread = threading.get_ident()
        return "# Converted\r\ncontent"

    parsed = await AnydocParser(converter=converter).parse(
        stored, "application/pdf"
    )

    assert converter_thread != event_loop_thread
    assert parsed.markdown == "# Converted\ncontent"


@pytest.mark.asyncio
async def test_anydoc_maps_converter_errors(tmp_path) -> None:
    stored = await LocalFileStore(tmp_path).put("p1", "d1", bytes_stream(b"document"))

    def converter(path) -> str:
        raise RuntimeError("converter detail must stay internal")

    with pytest.raises(DocumentParseFailed, match="document parsing failed"):
        await AnydocParser(converter=converter).parse(stored, "application/pdf")
