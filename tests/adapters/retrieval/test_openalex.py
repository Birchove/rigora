from datetime import date, datetime, timezone

import httpx
import pytest

from research_mentor.adapters.openalex.client import OpenAlexRetriever
from research_mentor.domain.evidence import RetrievalDiagnostics
from research_mentor.errors import LiteratureSearchUnavailable


OPENALEX_PAGE = {
    "results": [
        {
            "id": "https://openalex.org/W1",
            "doi": "https://doi.org/10.1/example",
            "title": "A Cache Study",
            "publication_date": "2025-06-01",
            "cited_by_count": 12,
            "authorships": [
                {"author": {"display_name": "Ada Researcher"}},
                {"author": {"display_name": "Lin Scholar"}},
            ],
            "primary_location": {"landing_page_url": "https://example.test/paper"},
            "abstract_inverted_index": {
                "Cache": [0],
                "latency": [1],
                "improves": [2],
            },
        }
    ]
}
EMPTY_PAGE = {"results": []}


async def immediate_sleep(delay: float) -> None:
    return None


@pytest.mark.asyncio
async def test_openalex_maps_work_to_literature_record(respx_mock) -> None:
    respx_mock.get("https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=OPENALEX_PAGE)
    )
    async with httpx.AsyncClient() as client:
        records = await OpenAlexRetriever(
            client,
            mailto="dev@example.com",
            now=lambda: datetime(2026, 8, 30, tzinfo=timezone.utc),
        ).search("cache invalidation", limit=2)

    assert records[0].title == "A Cache Study"
    assert records[0].doi == "https://doi.org/10.1/example"
    assert records[0].provider == "openalex"
    assert records[0].provider_id == "https://openalex.org/W1"
    assert records[0].publication_date == date(2025, 6, 1)
    assert records[0].cited_by_count == 12
    assert records[0].query_id == "q1"
    assert records[0].abstract == "Cache latency improves"


@pytest.mark.asyncio
async def test_openalex_sends_fixed_bounded_query_parameters(respx_mock) -> None:
    route = respx_mock.get("https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=EMPTY_PAGE)
    )
    async with httpx.AsyncClient() as client:
        await OpenAlexRetriever(client, mailto="dev@example.com").search(
            "cache invalidation", limit=80
        )

    request = route.calls[0].request
    assert request.url.params["search"] == "cache invalidation"
    assert request.url.params["per-page"] == "50"
    assert request.url.params["mailto"] == "dev@example.com"
    assert request.url.params["select"].startswith("id,doi,title,")
    assert "api_key" not in request.url.params
    assert request.headers.get("authorization") is None


@pytest.mark.asyncio
async def test_openalex_sends_api_key_as_query_and_bearer(respx_mock) -> None:
    route = respx_mock.get("https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=EMPTY_PAGE)
    )
    async with httpx.AsyncClient() as client:
        await OpenAlexRetriever(client, api_key="test-openalex-key").search("x")

    request = route.calls[0].request
    assert request.url.params["api_key"] == "test-openalex-key"
    assert request.headers["authorization"] == "Bearer test-openalex-key"


@pytest.mark.asyncio
async def test_openalex_retries_429_once_and_honors_retry_after(respx_mock) -> None:
    delays: list[float] = []

    async def capture_sleep(delay: float) -> None:
        delays.append(delay)

    route = respx_mock.get("https://api.openalex.org/works").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "2"}),
            httpx.Response(200, json=EMPTY_PAGE),
        ]
    )
    async with httpx.AsyncClient() as client:
        records = await OpenAlexRetriever(
            client,
            sleep=capture_sleep,
        ).search("x")

    assert records == []
    assert route.call_count == 2
    assert delays == [2.0]


@pytest.mark.asyncio
async def test_openalex_does_not_retry_semantic_4xx(respx_mock) -> None:
    route = respx_mock.get("https://api.openalex.org/works").mock(
        return_value=httpx.Response(400, json={"error": "bad query"})
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(LiteratureSearchUnavailable):
            await OpenAlexRetriever(client, sleep=immediate_sleep).search("x")

    assert route.call_count == 1


@pytest.mark.asyncio
async def test_search_many_deduplicates_and_keeps_per_query_diagnostics(
    respx_mock,
) -> None:
    duplicate_without_optional_ids = {
        "results": [
            {
                **OPENALEX_PAGE["results"][0],
                "doi": None,
                "primary_location": None,
                "abstract_inverted_index": None,
            }
        ]
    }
    respx_mock.get("https://api.openalex.org/works").mock(
        side_effect=[
            httpx.Response(200, json=OPENALEX_PAGE),
            httpx.Response(200, json=duplicate_without_optional_ids),
        ]
    )
    async with httpx.AsyncClient() as client:
        records, diagnostics = await OpenAlexRetriever(client).search_many(
            ["cache", "latency"]
        )

    assert len(records) == 1
    assert [item.query for item in diagnostics] == ["cache", "latency"]
    assert [item.status for item in diagnostics] == ["ok", "ok"]


@pytest.mark.asyncio
async def test_missing_doi_url_and_abstract_remain_none(respx_mock) -> None:
    work = {
        **OPENALEX_PAGE["results"][0],
        "doi": None,
        "primary_location": None,
        "abstract_inverted_index": None,
    }
    respx_mock.get("https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json={"results": [work]})
    )
    async with httpx.AsyncClient() as client:
        record = (await OpenAlexRetriever(client).search("x"))[0]

    assert record.doi is None
    assert record.url is None
    assert record.abstract is None


@pytest.mark.asyncio
async def test_malformed_provider_payload_is_typed_unavailable(respx_mock) -> None:
    respx_mock.get("https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, content=b"not-json")
    )
    retriever: OpenAlexRetriever
    async with httpx.AsyncClient() as client:
        retriever = OpenAlexRetriever(client)
        with pytest.raises(LiteratureSearchUnavailable):
            await retriever.search("x")

    assert retriever.last_diagnostics is not None
    assert retriever.last_diagnostics.status == "unavailable"
    assert retriever.last_diagnostics.limitation == "malformed_response"


def test_retrieval_diagnostics_distinguishes_empty_and_unavailable() -> None:
    empty = RetrievalDiagnostics(
        query="x",
        provider="openalex",
        candidate_count=0,
        selected_count=0,
        top_relevance=None,
        status="empty",
    )
    unavailable = RetrievalDiagnostics(
        query="x",
        provider="openalex",
        candidate_count=0,
        selected_count=0,
        top_relevance=None,
        status="unavailable",
        limitation="timeout",
    )

    assert empty.status == "empty"
    assert unavailable.status == "unavailable"
