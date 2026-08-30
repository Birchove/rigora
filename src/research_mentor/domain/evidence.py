"""Evidence and literature references."""

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


class EvidenceRef(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    source_type: SourceType
    url: str | None = None
    doi: str | None = None
    support: str
