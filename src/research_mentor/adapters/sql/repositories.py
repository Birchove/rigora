"""Async SQL repositories sharing one unit-of-work session."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from research_mentor.adapters.sql.mappers import (
    agent_output_to_row,
    event_to_row,
    outbox_to_row,
    session_from_payload,
    session_payload,
)
from research_mentor.adapters.sql.models import (
    AgentOutputRow,
    OutboxEventRow,
    ProcessedCommandRow,
    ResearchSessionRow,
    SessionEventRow,
)
from research_mentor.errors import ConcurrencyConflict, SessionNotFoundError
from research_mentor.harness.state import ResearchSession, SessionEvent
from research_mentor.ports.events import OutboxEvent
from research_mentor.ports.repository import AgentOutputRecord, ProcessedCommand


class SqlSessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, session_id: str) -> ResearchSession | None:
        row = await self._db.get(ResearchSessionRow, session_id)
        if row is None:
            return None
        return session_from_payload(row.payload)

    async def save(
        self,
        session: ResearchSession,
        *,
        expected_version: int,
    ) -> None:
        statement = (
            update(ResearchSessionRow)
            .where(
                ResearchSessionRow.session_id == session.session_id,
                ResearchSessionRow.version == expected_version,
            )
            .values(
                payload=session_payload(session),
                phase=session.phase.value,
                updated_at=datetime.now(timezone.utc),
                version=expected_version + 1,
            )
        )
        result = await self._db.execute(statement)
        if result.rowcount != 1:
            raise ConcurrencyConflict(session.session_id, expected_version)


class SqlSessionEventRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def append(self, event: SessionEvent) -> None:
        project_id = await self._db.scalar(
            select(ResearchSessionRow.project_id).where(
                ResearchSessionRow.session_id == event.session_id
            )
        )
        if project_id is None:
            raise SessionNotFoundError(f"Session not found: {event.session_id}")
        latest_sequence = await self._db.scalar(
            select(func.max(SessionEventRow.sequence)).where(
                SessionEventRow.project_id == project_id
            )
        )
        self._db.add(
            event_to_row(
                event,
                project_id=project_id,
                sequence=(latest_sequence or 0) + 1,
            )
        )


class SqlOutboxRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def append(self, event: OutboxEvent) -> None:
        self._db.add(outbox_to_row(event))

    async def list_pending(self, *, limit: int) -> list[OutboxEvent]:
        rows = (
            await self._db.scalars(
                select(OutboxEventRow)
                .where(OutboxEventRow.published_at.is_(None))
                .order_by(OutboxEventRow.created_at, OutboxEventRow.outbox_id)
                .limit(limit)
            )
        ).all()
        return [
            OutboxEvent(
                outbox_id=row.outbox_id,
                session_event_id=row.session_event_id,
                project_id=row.project_id,
                topic=row.topic,
                payload=row.payload,
                created_at=row.created_at,
                published_at=row.published_at,
            )
            for row in rows
        ]

    async def mark_published(self, outbox_id: str, published_at: datetime) -> None:
        await self._db.execute(
            update(OutboxEventRow)
            .where(OutboxEventRow.outbox_id == outbox_id)
            .values(published_at=published_at)
        )


class SqlAgentOutputRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def add(self, output: AgentOutputRecord) -> None:
        self._db.add(agent_output_to_row(output))

    async def list_for_run(self, run_id: str) -> list[AgentOutputRecord]:
        rows = (
            await self._db.scalars(
                select(AgentOutputRow)
                .where(AgentOutputRow.run_id == run_id)
                .order_by(AgentOutputRow.created_at, AgentOutputRow.output_id)
            )
        ).all()
        return [
            AgentOutputRecord(
                output_id=row.output_id,
                run_id=row.run_id,
                project_id=row.project_id,
                agent_name=row.agent_name,
                prompt_version=row.prompt_version,
                session_version=row.session_version,
                structured_payload=row.structured_payload,
                created_at=row.created_at,
            )
            for row in rows
        ]


class SqlProcessedCommandRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find(
        self, project_id: str, command_id: str
    ) -> ProcessedCommand | None:
        row = await self._db.scalar(
            select(ProcessedCommandRow).where(
                ProcessedCommandRow.project_id == project_id,
                ProcessedCommandRow.command_id == command_id,
            )
        )
        if row is None:
            return None
        return ProcessedCommand(
            project_id=row.project_id,
            command_id=row.command_id,
            receipt=row.receipt,
            run_id=row.run_id,
            created_at=row.created_at,
        )

    async def add(self, command: ProcessedCommand) -> None:
        self._db.add(
            ProcessedCommandRow(
                processed_id=str(uuid4()),
                project_id=command.project_id,
                command_id=command.command_id,
                receipt=command.receipt,
                run_id=command.run_id,
                created_at=command.created_at,
            )
        )
