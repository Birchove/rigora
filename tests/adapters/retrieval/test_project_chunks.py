from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from research_mentor.adapters.sql.base import Base
from research_mentor.adapters.sql.models import (
    DocumentChunkRow,
    DocumentRow,
    ProjectRow,
)
from research_mentor.application.retrieval_service import RetrievalService
from research_mentor.ports.retrieval import RankResult


NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


class SpyRanker:
    def __init__(self) -> None:
        self.chunk_ids: list[str] = []

    def rank(self, query, chunks, *, limit) -> RankResult:
        self.chunk_ids = [chunk.chunk_id for chunk in chunks]
        return RankResult(status="ok", items=[])


@pytest_asyncio.fixture
async def chunk_session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'chunks.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory.begin() as db:
        for project_id, document_id in (("p1", "d1"), ("p2", "d2")):
            db.add(
                ProjectRow(
                    project_id=project_id,
                    title=project_id,
                    domain="computer science",
                    session_id=f"s-{project_id}",
                    version=1,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            db.add(
                DocumentRow(
                    document_id=document_id,
                    project_id=project_id,
                    original_name="notes.md",
                    media_type="text/markdown",
                    size_bytes=10,
                    sha256="0" * 64,
                    status="ready",
                    storage_path=f"/{document_id}/source.bin",
                    created_at=NOW,
                )
            )
            db.add(
                DocumentChunkRow(
                    chunk_id=f"c-{project_id}",
                    document_id=document_id,
                    ordinal=0,
                    heading_path=["结果"],
                    markdown=f"{project_id} 的缓存结果",
                )
            )
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_retrieval_service_recalls_only_project_chunks(
    chunk_session_factory,
) -> None:
    ranker = SpyRanker()
    service = RetrievalService(chunk_session_factory, ranker, candidate_limit=20)

    await service.retrieve("p1", "缓存", limit=5)

    assert ranker.chunk_ids == ["c-p1"]


@pytest.mark.asyncio
async def test_retrieval_service_passes_empty_candidates_to_one_ranker(
    chunk_session_factory,
) -> None:
    ranker = SpyRanker()
    service = RetrievalService(chunk_session_factory, ranker)

    result = await service.retrieve("missing", "缓存", limit=5)

    assert ranker.chunk_ids == []
    assert result.status == "ok"
