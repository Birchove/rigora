"""Thread-isolated adapter for the Anydoc converter."""

import asyncio
from collections.abc import Callable
from pathlib import Path

import anydoc

from research_mentor.domain.documents import ParsedDocument
from research_mentor.errors import DocumentParseFailed
from research_mentor.ports.files import StoredFile


class AnydocParser:
    def __init__(
        self,
        converter: Callable[[Path], str] = anydoc.to_markdown,
    ) -> None:
        self._converter = converter

    async def parse(
        self,
        stored_file: StoredFile,
        media_type: str,
    ) -> ParsedDocument:
        try:
            markdown = await asyncio.to_thread(
                self._converter,
                stored_file.path,
            )
        except Exception as exc:
            raise DocumentParseFailed("document parsing failed") from exc
        return ParsedDocument(
            markdown=markdown.replace("\r\n", "\n").replace("\r", "\n"),
            parser_metadata={"parser": "anydoc", "media_type": media_type},
        )
