"""Document parsing boundary and normalized parser output."""

from typing import Protocol

from research_mentor.domain.documents import DocumentChunk, ParsedDocument
from research_mentor.ports.files import StoredFile


class DocumentParserPort(Protocol):
    async def parse(
        self, stored_file: StoredFile, media_type: str
    ) -> ParsedDocument: ...
