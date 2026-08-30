"""Literature retrieval port."""

from typing import Protocol

from research_mentor.domain.evidence import LiteratureRecord


class LiteratureSearchPort(Protocol):
    def search(self, query: str, *, limit: int) -> list[LiteratureRecord]:
        raise NotImplementedError
