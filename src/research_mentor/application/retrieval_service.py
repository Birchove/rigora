"""Project-scoped document candidate recall and ranking."""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from research_mentor.adapters.sql.models import DocumentChunkRow, DocumentRow
from research_mentor.domain.documents import DocumentChunk
from research_mentor.hyperparameters import RETRIEVAL_CANDIDATE_LIMIT
from research_mentor.ports.retrieval import RankResult, RetrievalRankerPort


class RetrievalService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ranker: RetrievalRankerPort,
        *,
        candidate_limit: int = RETRIEVAL_CANDIDATE_LIMIT,
    ) -> None:
        if candidate_limit < 1:
            raise ValueError("candidate_limit must be positive")
        self._session_factory = session_factory
        self._ranker = ranker
        self._candidate_limit = candidate_limit

    async def retrieve(
        self,
        project_id: str,
        query: str,
        *,
        limit: int,
    ) -> RankResult:
        async with self._session_factory() as db:
            rows = (
                await db.scalars(
                    select(DocumentChunkRow)
                    .join(
                        DocumentRow,
                        DocumentRow.document_id == DocumentChunkRow.document_id,
                    )
                    .where(DocumentRow.project_id == project_id)
                    .order_by(
                        DocumentChunkRow.document_id,
                        DocumentChunkRow.ordinal,
                        DocumentChunkRow.chunk_id,
                    )
                    .limit(self._candidate_limit)
                )
            ).all()
        chunks = [
            DocumentChunk(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                ordinal=row.ordinal,
                heading_path=row.heading_path,
                markdown=row.markdown,
            )
            for row in rows
        ]
        return await asyncio.to_thread(
            self._ranker.rank,
            query,
            chunks,
            limit=limit,
        )
