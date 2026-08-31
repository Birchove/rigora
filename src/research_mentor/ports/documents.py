"""Document parsing boundary and normalized parser output."""

from typing import Protocol

from pydantic import BaseModel, Field, JsonValue

from research_mentor.ports.files import StoredFile


class ParsedDocument(BaseModel):
    markdown: str
    parser_metadata: dict[str, JsonValue] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    ordinal: int = Field(ge=0)
    heading_path: list[str] = Field(default_factory=list)
    markdown: str


class DocumentParserPort(Protocol):
    async def parse(
        self, stored_file: StoredFile, media_type: str
    ) -> ParsedDocument: ...
