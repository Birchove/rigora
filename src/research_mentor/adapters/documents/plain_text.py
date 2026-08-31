"""UTF-8 plain text and Markdown parser."""

import asyncio

from research_mentor.errors import DocumentParseFailed
from research_mentor.domain.documents import ParsedDocument
from research_mentor.ports.files import StoredFile


SUPPORTED_MEDIA_TYPES = {
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "application/markdown",
}


class PlainTextParser:
    async def parse(
        self,
        stored_file: StoredFile,
        media_type: str,
    ) -> ParsedDocument:
        if media_type not in SUPPORTED_MEDIA_TYPES:
            raise DocumentParseFailed("document parsing failed: unsupported media type")
        try:
            content = await asyncio.to_thread(stored_file.path.read_bytes)
            markdown = content.decode("utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            raise DocumentParseFailed("document parsing failed") from exc
        return ParsedDocument(
            markdown=markdown.replace("\r\n", "\n").replace("\r", "\n"),
            parser_metadata={"parser": "plain_text"},
        )
