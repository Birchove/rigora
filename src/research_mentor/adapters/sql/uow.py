"""SQLAlchemy unit of work."""

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from research_mentor.adapters.sql.repositories import (
    SqlAgentOutputRepository,
    SqlAgentRunRepository,
    SqlDocumentParseJobRepository,
    SqlDocumentRepository,
    SqlLiteratureRepository,
    SqlOutboxRepository,
    SqlProcessedCommandRepository,
    SqlProjectRepository,
    SqlSessionEventRepository,
    SqlSessionRepository,
)


class SqlUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._db: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self._db = self._session_factory()
        self.projects = SqlProjectRepository(self._db)
        self.sessions = SqlSessionRepository(self._db)
        self.processed_commands = SqlProcessedCommandRepository(self._db)
        self.events = SqlSessionEventRepository(self._db)
        self.outbox = SqlOutboxRepository(self._db)
        self.agent_outputs = SqlAgentOutputRepository(self._db)
        self.runs = SqlAgentRunRepository(self._db)
        self.documents = SqlDocumentRepository(self._db)
        self.document_parse_jobs = SqlDocumentParseJobRepository(self._db)
        self.literature = SqlLiteratureRepository(self._db)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._db is None:
            return
        try:
            if exc_type is None:
                await self._db.commit()
            else:
                await self._db.rollback()
        finally:
            await self._db.close()
            self._db = None
