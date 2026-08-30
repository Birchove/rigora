"""In-memory literature search adapter."""

from research_mentor.domain.evidence import LiteratureRecord


class MemoryLiteratureSearchAdapter:
    def __init__(self) -> None:
        self._results: dict[str, list[LiteratureRecord]] = {}

    def set_results(self, query: str, results: list[LiteratureRecord]) -> None:
        self._results[query] = [record.model_copy(deep=True) for record in results]

    def search(self, query: str, *, limit: int) -> list[LiteratureRecord]:
        if limit <= 0:
            return []
        return [record.model_copy(deep=True) for record in self._results.get(query, [])[:limit]]
