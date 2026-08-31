"""Document domain models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, JsonValue


DocumentStatus = Literal["uploaded", "parsing", "ready", "failed"]


class UploadedDocument(BaseModel):
    document_id: str
    project_id: str
    original_name: str
    media_type: str
    size_bytes: int = Field(ge=0)
    sha256: str
    status: DocumentStatus
    created_at: datetime
    error_message: str | None = None


class ParsedDocument(BaseModel):
    markdown: str
    parser_metadata: dict[str, JsonValue] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    ordinal: int = Field(ge=0)
    heading_path: list[str] = Field(default_factory=list)
    markdown: str
