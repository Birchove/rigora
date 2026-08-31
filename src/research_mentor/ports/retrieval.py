"""Literature and project-document retrieval ports."""

from collections.abc import Sequence
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, model_validator

from research_mentor.domain.documents import DocumentChunk
from research_mentor.domain.evidence import LiteratureRecord


class LiteratureSearchPort(Protocol):
    async def search(
        self, query: str, *, limit: int = 10
    ) -> list[LiteratureRecord]: ...


class RankedChunk(BaseModel):
    chunk: DocumentChunk
    score: float = Field(ge=0.0, le=1.0)


class RankResult(BaseModel):
    status: Literal["ok", "unavailable"]
    items: list[RankedChunk] = Field(default_factory=list)
    limitation: str | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "RankResult":
        if self.status == "unavailable":
            if self.items:
                raise ValueError("unavailable rank result cannot contain items")
            if self.limitation is None or not self.limitation.strip():
                raise ValueError("unavailable rank result requires limitation")
        return self


@runtime_checkable
class RetrievalRankerPort(Protocol):
    def rank(
        self,
        query: str,
        chunks: Sequence[DocumentChunk],
        *,
        limit: int,
    ) -> RankResult: ...
