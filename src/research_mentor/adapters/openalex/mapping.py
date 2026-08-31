"""Pure OpenAlex response mapping and deduplication."""

from datetime import date, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import NAMESPACE_URL, uuid5

from research_mentor.domain.evidence import LiteratureRecord


def restore_abstract(index: dict[str, list[int]] | None) -> str | None:
    if not index:
        return None
    positioned = [
        (position, word)
        for word, positions in index.items()
        for position in positions
    ]
    return " ".join(word for _, word in sorted(positioned)) or None


def map_work(
    work: dict[str, Any],
    *,
    query_id: str,
    retrieved_at: datetime,
) -> LiteratureRecord:
    provider_id = work.get("id")
    doi = work.get("doi")
    location = work.get("primary_location") or {}
    url = location.get("landing_page_url")
    publication_date = _parse_date(work.get("publication_date"))
    abstract = restore_abstract(work.get("abstract_inverted_index"))
    identity = provider_id or doi or url or work.get("title") or query_id
    return LiteratureRecord(
        record_id=str(uuid5(NAMESPACE_URL, f"openalex:{identity}")),
        provider="openalex",
        provider_id=provider_id,
        query_id=query_id,
        retrieved_at=retrieved_at,
        title=work.get("title") or "",
        authors=[
            author["author"]["display_name"]
            for author in work.get("authorships") or []
            if author.get("author", {}).get("display_name")
        ],
        year=publication_date.year if publication_date else None,
        publication_date=publication_date,
        source_type="paper",
        url=url,
        doi=doi,
        abstract=abstract,
        cited_by_count=work.get("cited_by_count"),
        summary=abstract or "",
        relevance="",
    )


def deduplicate(records: list[LiteratureRecord]) -> list[LiteratureRecord]:
    seen_provider_ids: set[str] = set()
    seen_dois: set[str] = set()
    seen_urls: set[str] = set()
    unique: list[LiteratureRecord] = []
    for record in records:
        provider_id = (record.provider_id or "").strip().lower()
        doi = _normalize_doi(record.doi)
        url = _normalize_url(record.url)
        if (
            (provider_id and provider_id in seen_provider_ids)
            or (doi and doi in seen_dois)
            or (url and url in seen_urls)
        ):
            continue
        unique.append(record)
        if provider_id:
            seen_provider_ids.add(provider_id)
        if doi:
            seen_dois.add(doi)
        if url:
            seen_urls.add(url)
    return unique


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _normalize_doi(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            return normalized[len(prefix) :]
    return normalized


def _normalize_url(value: str | None) -> str:
    if not value:
        return ""
    parts = urlsplit(value.strip())
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            parts.query,
            "",
        )
    )
