"""Document domain models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
