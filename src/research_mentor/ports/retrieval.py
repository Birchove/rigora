"""Literature retrieval port."""

from typing import Protocol

from research_mentor.domain.evidence import LiteratureRecord


class LiteratureSearchPort(Protocol):
    async def search(
        self, query: str, *, limit: int = 10
    ) -> list[LiteratureRecord]: ...
