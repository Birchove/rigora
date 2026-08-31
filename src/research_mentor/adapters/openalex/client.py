"""Async OpenAlex client with bounded retry behavior."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, timezone

import httpx

from research_mentor.adapters.openalex.mapping import deduplicate, map_work
from research_mentor.domain.evidence import LiteratureRecord, RetrievalDiagnostics
from research_mentor.errors import LiteratureSearchUnavailable


OPENALEX_URL = "https://api.openalex.org/works"
SELECT_FIELDS = (
    "id,doi,title,publication_date,cited_by_count,authorships,"
    "primary_location,abstract_inverted_index"
)
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


class OpenAlexRetriever:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        mailto: str | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        max_attempts: int = 3,
    ) -> None:
        self._client = client
        self._mailto = mailto
        self._sleep = sleep
        self._now = now
        self._max_attempts = max_attempts
        self._query_sequence = 0
        self.last_diagnostics: RetrievalDiagnostics | None = None

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[LiteratureRecord]:
        self._query_sequence += 1
        query_id = f"q{self._query_sequence}"
        if limit <= 0:
            self.last_diagnostics = self._diagnostics(query, [], status="empty")
            return []
        params = {
            "search": query,
            "per-page": min(limit, 50),
            "select": SELECT_FIELDS,
        }
        if self._mailto:
            params["mailto"] = self._mailto

        response = await self._request(query, params)
        retrieved_at = self._now()
        try:
            results = response.json().get("results", [])
            if not isinstance(results, list):
                raise TypeError("OpenAlex results must be a list")
            records = deduplicate(
                [
                    map_work(
                        work,
                        query_id=query_id,
                        retrieved_at=retrieved_at,
                    )
                    for work in results
                ]
            )[:limit]
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            self._set_unavailable(query, "malformed_response")
            raise LiteratureSearchUnavailable(
                "OpenAlex returned a malformed response"
            ) from exc
        status = "ok" if records else "empty"
        self.last_diagnostics = self._diagnostics(query, records, status=status)
        return records

    async def search_many(
        self,
        queries: Sequence[str],
        *,
        limit: int = 10,
    ) -> tuple[list[LiteratureRecord], list[RetrievalDiagnostics]]:
        records: list[LiteratureRecord] = []
        diagnostics: list[RetrievalDiagnostics] = []
        for query in queries:
            try:
                records.extend(await self.search(query, limit=limit))
            except LiteratureSearchUnavailable:
                pass
            if self.last_diagnostics is not None:
                diagnostics.append(self.last_diagnostics.model_copy(deep=True))
        return deduplicate(records), diagnostics

    async def _request(
        self,
        query: str,
        params: dict[str, str | int],
    ) -> httpx.Response:
        for attempt in range(self._max_attempts):
            try:
                response = await self._client.get(OPENALEX_URL, params=params)
            except httpx.TransportError as exc:
                self._set_unavailable(query, "transport_error")
                raise LiteratureSearchUnavailable("OpenAlex request failed") from exc
            if response.status_code not in RETRYABLE_STATUS_CODES:
                if response.is_error:
                    self._set_unavailable(query, f"http_{response.status_code}")
                    raise LiteratureSearchUnavailable("OpenAlex request failed")
                return response
            if attempt + 1 == self._max_attempts:
                self._set_unavailable(query, f"http_{response.status_code}")
                raise LiteratureSearchUnavailable("OpenAlex retry limit reached")
            await self._sleep(self._retry_delay(response, attempt))
        raise AssertionError("unreachable")

    def _set_unavailable(self, query: str, limitation: str) -> None:
        self.last_diagnostics = RetrievalDiagnostics(
            query=query,
            provider="openalex",
            candidate_count=0,
            selected_count=0,
            top_relevance=None,
            status="unavailable",
            limitation=limitation,
        )

    @staticmethod
    def _diagnostics(
        query: str,
        records: list[LiteratureRecord],
        *,
        status: str,
    ) -> RetrievalDiagnostics:
        return RetrievalDiagnostics(
            query=query,
            provider="openalex",
            candidate_count=len(records),
            selected_count=len(records),
            top_relevance=None,
            status=status,
        )

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        return 0.5 * (2**attempt)
