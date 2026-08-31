"""Evidence and literature references."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal["paper", "book", "website", "dataset", "other"]


class LiteratureRecord(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    source_type: SourceType
    url: str | None = None
    doi: str | None = None
    abstract: str | None = None
    summary: str
    relevance: str
    key_findings: list[str] = Field(default_factory=list)
    record_id: str | None = None
    provider: str | None = None
    provider_id: str | None = None
    publication_date: date | None = None
    cited_by_count: int | None = Field(default=None, ge=0)
    retrieved_at: datetime | None = None
    query_id: str | None = None


class RetrievalDiagnostics(BaseModel):
    query: str
    provider: str
    candidate_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    top_relevance: float | None = Field(default=None, ge=0.0, le=1.0)
    status: Literal["ok", "empty", "unavailable"]
    limitation: str | None = None


class EvidenceRef(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    source_type: SourceType
    url: str | None = None
    doi: str | None = None
    support: str
