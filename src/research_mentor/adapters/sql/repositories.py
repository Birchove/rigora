"""Async SQL repositories sharing one unit-of-work session."""

from __future__ import annotations

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
    AgentRunRow,
    DocumentChunkRow,
    DocumentParseJobRow,
    DocumentRow,
    LiteratureRecordRow,
    ProjectLiteratureRow,
    OutboxEventRow,
    ProcessedCommandRow,
    ProjectRow,
    ResearchSessionRow,
    SessionEventRow,
)
from research_mentor.errors import ConcurrencyConflict, SessionNotFoundError
from research_mentor.domain.jobs import AgentRun
from research_mentor.domain.documents import DocumentChunk, DocumentParseJob, UploadedDocument
from research_mentor.domain.evidence import LiteratureRecord
from research_mentor.domain.projects import ResearchProject
from research_mentor.harness.state import ResearchSession, SessionEvent
from research_mentor.ports.events import OutboxEvent, PersistedPublicEvent
from research_mentor.ports.repository import AgentOutputRecord, ProcessedCommand


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class SqlSessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def add(self, session: ResearchSession, *, project_id: str) -> None:
        self._db.add(
            ResearchSessionRow(
                session_id=session.session_id,
                project_id=project_id,
                version=1,
                phase=session.phase.value,
                updated_at=datetime.now(timezone.utc),
                payload=session_payload(session),
            )
        )

    async def get(self, session_id: str) -> ResearchSession | None:
        row = await self._db.get(ResearchSessionRow, session_id)
        if row is None:
            return None
        return session_from_payload(row.payload)

    async def row_version(self, session_id: str) -> int:
        row = await self._db.get(ResearchSessionRow, session_id)
        if row is None:
            raise SessionNotFoundError(f"Session not found: {session_id}")
        return row.version

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


class SqlProjectRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def add(self, project: ResearchProject) -> None:
        self._db.add(
            ProjectRow(
                project_id=project.project_id,
                title=project.title,
                domain=project.domain,
                session_id=project.session_id,
                version=project.version,
                is_demo=project.is_demo,
                created_at=project.created_at,
                updated_at=project.updated_at,
            )
        )

    async def get(self, project_id: str) -> ResearchProject | None:
        row = await self._db.get(ProjectRow, project_id)
        if row is None:
            return None
        return ResearchProject(
            project_id=row.project_id,
            title=row.title,
            domain=row.domain,
            session_id=row.session_id,
            version=row.version,
            is_demo=row.is_demo,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def list(self) -> list[ResearchProject]:
        rows = (
            await self._db.scalars(
                select(ProjectRow).order_by(
                    ProjectRow.updated_at.desc(), ProjectRow.project_id
                )
            )
        ).all()
        return [
            ResearchProject(
                project_id=row.project_id,
                title=row.title,
                domain=row.domain,
                session_id=row.session_id,
                version=row.version,
                is_demo=row.is_demo,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]

    async def save(
        self, project: ResearchProject, *, expected_version: int
    ) -> None:
        statement = (
            update(ProjectRow)
            .where(
                ProjectRow.project_id == project.project_id,
                ProjectRow.version == expected_version,
            )
            .values(
                title=project.title,
                domain=project.domain,
                session_id=project.session_id,
                version=project.version,
                is_demo=project.is_demo,
                updated_at=project.updated_at,
            )
        )
        result = await self._db.execute(statement)
        if result.rowcount != 1:
            raise ConcurrencyConflict(project.project_id, expected_version)


class SqlDocumentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @staticmethod
    def _document(row: DocumentRow) -> UploadedDocument:
        return UploadedDocument(
            document_id=row.document_id,
            project_id=row.project_id,
            original_name=row.original_name,
            media_type=row.media_type,
            size_bytes=row.size_bytes,
            sha256=row.sha256,
            status=row.status,
            created_at=_as_utc(row.created_at),
            error_message=row.error_message,
        )

    async def add(self, document: UploadedDocument, *, storage_path: str) -> None:
        self._db.add(DocumentRow(**document.model_dump(mode="python"), storage_path=storage_path))

    async def get(self, document_id: str, *, project_id: str) -> UploadedDocument | None:
        row = await self._db.scalar(select(DocumentRow).where(
            DocumentRow.document_id == document_id,
            DocumentRow.project_id == project_id,
        ))
        return self._document(row) if row is not None else None

    async def storage_path(self, document_id: str, *, project_id: str) -> str | None:
        return await self._db.scalar(select(DocumentRow.storage_path).where(
            DocumentRow.document_id == document_id,
            DocumentRow.project_id == project_id,
        ))

    async def list(self, project_id: str) -> list[UploadedDocument]:
        rows = (await self._db.scalars(select(DocumentRow).where(
            DocumentRow.project_id == project_id
        ).order_by(DocumentRow.created_at, DocumentRow.document_id))).all()
        return [self._document(row) for row in rows]

    async def total_size(self, project_id: str) -> int:
        return int(await self._db.scalar(select(func.coalesce(func.sum(DocumentRow.size_bytes), 0)).where(
            DocumentRow.project_id == project_id
        )) or 0)

    async def set_status(
        self, document_id: str, *, project_id: str, status: str, error_message: str | None = None
    ) -> None:
        result = await self._db.execute(update(DocumentRow).where(
            DocumentRow.document_id == document_id,
            DocumentRow.project_id == project_id,
        ).values(status=status, error_message=error_message))
        if result.rowcount != 1:
            raise SessionNotFoundError(f"Document not found: {document_id}")

    async def replace_chunks(self, document_id: str, chunks: list[DocumentChunk]) -> None:
        from sqlalchemy import delete
        await self._db.execute(delete(DocumentChunkRow).where(DocumentChunkRow.document_id == document_id))
        self._db.add_all([DocumentChunkRow(**chunk.model_dump(mode="python")) for chunk in chunks])

    async def delete(self, document_id: str, *, project_id: str) -> bool:
        from sqlalchemy import delete
        result = await self._db.execute(delete(DocumentRow).where(
            DocumentRow.document_id == document_id,
            DocumentRow.project_id == project_id,
        ))
        return result.rowcount == 1


class SqlDocumentParseJobRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @staticmethod
    def _job(row: DocumentParseJobRow) -> DocumentParseJob:
        return DocumentParseJob(
            job_id=row.job_id, document_id=row.document_id, project_id=row.project_id,
            status=row.status, attempt=row.attempt, created_at=_as_utc(row.created_at),
            started_at=_as_utc(row.started_at), finished_at=_as_utc(row.finished_at),
            error_message=row.error_message,
        )

    async def add(self, job: DocumentParseJob) -> None:
        self._db.add(DocumentParseJobRow(**job.model_dump(mode="python")))

    async def next_attempt(self, document_id: str) -> int:
        value = await self._db.scalar(select(func.max(DocumentParseJobRow.attempt)).where(
            DocumentParseJobRow.document_id == document_id
        ))
        return int(value or 0) + 1

    async def get(self, job_id: str) -> DocumentParseJob | None:
        row = await self._db.get(DocumentParseJobRow, job_id)
        return self._job(row) if row is not None else None

    async def latest_for_document(self, document_id: str) -> DocumentParseJob | None:
        row = await self._db.scalar(select(DocumentParseJobRow).where(
            DocumentParseJobRow.document_id == document_id
        ).order_by(DocumentParseJobRow.attempt.desc()).limit(1))
        return self._job(row) if row is not None else None

    async def save(self, job: DocumentParseJob) -> None:
        await self._db.execute(update(DocumentParseJobRow).where(
            DocumentParseJobRow.job_id == job.job_id
        ).values(**job.model_dump(mode="python", exclude={"job_id"})))


class SqlLiteratureRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_for_project(self, project_id: str) -> list[LiteratureRecord]:
        rows = (await self._db.scalars(select(LiteratureRecordRow).join(
            ProjectLiteratureRow, ProjectLiteratureRow.record_id == LiteratureRecordRow.record_id
        ).where(ProjectLiteratureRow.project_id == project_id).order_by(LiteratureRecordRow.record_id))).all()
        return [LiteratureRecord.model_validate(row.payload) for row in rows]

    async def add_for_project(
        self,
        project_id: str,
        record: LiteratureRecord,
        *,
        selected: bool,
    ) -> None:
        if record.record_id is None or record.provider is None or record.provider_id is None:
            raise ValueError("persisted literature requires record/provider identifiers")
        if await self._db.get(LiteratureRecordRow, record.record_id) is None:
            self._db.add(
                LiteratureRecordRow(
                    record_id=record.record_id,
                    provider=record.provider,
                    provider_id=record.provider_id,
                    title=record.title,
                    payload=record.model_dump(mode="json"),
                    retrieved_at=record.retrieved_at or datetime.now(timezone.utc),
                )
            )
        link = await self._db.get(ProjectLiteratureRow, (project_id, record.record_id))
        if link is None:
            self._db.add(
                ProjectLiteratureRow(
                    project_id=project_id,
                    record_id=record.record_id,
                    query_id=record.query_id,
                    selected=selected,
                )
            )


class SqlAgentRunRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @staticmethod
    def _from_row(row: AgentRunRow) -> AgentRun:
        return AgentRun(
            run_id=row.run_id,
            project_id=row.project_id,
            command_id=row.command_id,
            agent_name=row.agent_name,
            status=row.status,
            attempt=row.attempt,
            started_at=_as_utc(row.started_at),
            finished_at=_as_utc(row.finished_at),
            public_message=row.public_message,
            error_code=row.error_code,
            available_at=_as_utc(row.available_at),
            lease_owner=row.lease_owner,
            lease_expires_at=_as_utc(row.lease_expires_at),
            row_version=row.row_version,
            cancel_requested=row.cancel_requested,
            input_snapshot=row.input_snapshot or {},
        )

    async def get(self, run_id: str) -> AgentRun | None:
        row = await self._db.get(AgentRunRow, run_id)
        return self._from_row(row) if row is not None else None

    async def find_active_for_project(self, project_id: str) -> AgentRun | None:
        row = await self._db.scalar(
            select(AgentRunRow)
            .where(
                AgentRunRow.project_id == project_id,
                AgentRunRow.status.in_(("queued", "running")),
            )
            .order_by(AgentRunRow.run_id)
            .limit(1)
        )
        return self._from_row(row) if row is not None else None

    async def add(self, run: AgentRun) -> None:
        self._db.add(AgentRunRow(**run.model_dump(mode="python")))

    async def save(self, run: AgentRun) -> None:
        result = await self._db.execute(
            update(AgentRunRow)
            .where(AgentRunRow.run_id == run.run_id)
            .values(**run.model_dump(mode="python", exclude={"run_id"}))
        )
        if result.rowcount != 1:
            raise SessionNotFoundError(f"Run not found: {run.run_id}")

    async def claim_next(
        self, *, worker_id: str, now: datetime, lease_expires_at: datetime
    ) -> AgentRun | None:
        run_ids = (
            await self._db.scalars(
                select(AgentRunRow.run_id)
                .where(
                    AgentRunRow.status == "queued",
                    (AgentRunRow.available_at.is_(None) | (AgentRunRow.available_at <= now)),
                )
                .order_by(AgentRunRow.available_at, AgentRunRow.run_id)
            )
        ).all()
        for run_id in run_ids:
            claimed = await self.claim(
                run_id,
                worker_id=worker_id,
                now=now,
                lease_expires_at=lease_expires_at,
            )
            if claimed is not None:
                return claimed
        return None

    async def claim(
        self,
        run_id: str,
        *,
        worker_id: str,
        now: datetime,
        lease_expires_at: datetime,
    ) -> AgentRun | None:
        row = await self._db.get(AgentRunRow, run_id)
        if row is None or row.status != "queued":
            return None
        available_at = _as_utc(row.available_at)
        if available_at is not None and available_at > now:
            return None
        result = await self._db.execute(
            update(AgentRunRow)
            .where(
                AgentRunRow.run_id == run_id,
                AgentRunRow.status == "queued",
                AgentRunRow.row_version == row.row_version,
            )
            .values(
                status="running",
                attempt=AgentRunRow.attempt + 1,
                started_at=func.coalesce(AgentRunRow.started_at, now),
                available_at=None,
                lease_owner=worker_id,
                lease_expires_at=lease_expires_at,
                row_version=AgentRunRow.row_version + 1,
            )
        )
        if result.rowcount != 1:
            return None
        await self._db.flush()
        refreshed = await self._db.get(AgentRunRow, run_id, populate_existing=True)
        return self._from_row(refreshed) if refreshed is not None else None

    async def renew_lease(
        self,
        run_id: str,
        *,
        worker_id: str,
        now: datetime,
        lease_expires_at: datetime,
    ) -> AgentRun | None:
        row = await self._db.get(AgentRunRow, run_id)
        if (
            row is None
            or row.status != "running"
            or row.lease_owner != worker_id
            or _as_utc(row.lease_expires_at) is None
            or _as_utc(row.lease_expires_at) <= now
        ):
            return None
        result = await self._db.execute(
            update(AgentRunRow)
            .where(
                AgentRunRow.run_id == run_id,
                AgentRunRow.status == "running",
                AgentRunRow.lease_owner == worker_id,
                AgentRunRow.lease_expires_at > now,
                AgentRunRow.row_version == row.row_version,
            )
            .values(
                lease_expires_at=lease_expires_at,
                row_version=AgentRunRow.row_version + 1,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            return None
        await self._db.flush()
        row = await self._db.get(AgentRunRow, run_id, populate_existing=True)
        return self._from_row(row) if row is not None else None

    async def request_cancel(self, run_id: str) -> bool:
        result = await self._db.execute(
            update(AgentRunRow)
            .where(
                AgentRunRow.run_id == run_id,
                AgentRunRow.status.in_(("queued", "running")),
            )
            .values(cancel_requested=True, row_version=AgentRunRow.row_version + 1)
        )
        return result.rowcount == 1

    async def finish(
        self,
        run_id: str,
        *,
        worker_id: str,
        expected_version: int,
        status: str,
        now: datetime,
        public_message: str,
        error_code: str | None,
    ) -> bool:
        owner_clause = (
            AgentRunRow.lease_owner == worker_id
            if worker_id
            else AgentRunRow.status == "queued"
        )
        result = await self._db.execute(
            update(AgentRunRow)
            .where(
                AgentRunRow.run_id == run_id,
                AgentRunRow.status.in_(("queued", "running")),
                AgentRunRow.row_version == expected_version,
                owner_clause,
            )
            .values(
                status=status,
                finished_at=now,
                public_message=public_message,
                error_code=error_code,
                lease_owner=None,
                lease_expires_at=None,
                row_version=AgentRunRow.row_version + 1,
            )
        )
        return result.rowcount == 1

    async def requeue_retry(
        self,
        run_id: str,
        *,
        worker_id: str,
        expected_version: int,
        available_at: datetime,
        public_message: str,
        error_code: str,
    ) -> bool:
        result = await self._db.execute(
            update(AgentRunRow)
            .where(
                AgentRunRow.run_id == run_id,
                AgentRunRow.status == "running",
                AgentRunRow.lease_owner == worker_id,
                AgentRunRow.row_version == expected_version,
            )
            .values(
                status="queued",
                available_at=available_at,
                lease_owner=None,
                lease_expires_at=None,
                public_message=public_message,
                error_code=error_code,
                row_version=AgentRunRow.row_version + 1,
            )
        )
        return result.rowcount == 1

    async def requeue_expired(self, *, now: datetime) -> tuple[str, ...]:
        candidates = (
            await self._db.execute(
                select(AgentRunRow.run_id, AgentRunRow.row_version)
                .where(
                    AgentRunRow.status == "running",
                    AgentRunRow.lease_expires_at <= now,
                )
                .order_by(AgentRunRow.run_id)
            )
        ).all()
        requeued: list[str] = []
        for run_id, row_version in candidates:
            result = await self._db.execute(
                update(AgentRunRow)
                .where(
                    AgentRunRow.run_id == run_id,
                    AgentRunRow.status == "running",
                    AgentRunRow.lease_expires_at <= now,
                    AgentRunRow.row_version == row_version,
                )
                .values(
                    status="queued",
                    available_at=now,
                    lease_owner=None,
                    lease_expires_at=None,
                    row_version=AgentRunRow.row_version + 1,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount == 1:
                requeued.append(run_id)
        return tuple(requeued)


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

    async def list_for_project_after(
        self, project_id: str, *, after: int
    ) -> list[PersistedPublicEvent]:
        rows = (
            await self._db.execute(
                select(SessionEventRow, OutboxEventRow.topic)
                .outerjoin(
                    OutboxEventRow,
                    OutboxEventRow.session_event_id == SessionEventRow.event_id,
                )
                .where(
                    SessionEventRow.project_id == project_id,
                    SessionEventRow.sequence > after,
                )
                .order_by(SessionEventRow.sequence)
            )
        ).all()
        return [
            PersistedPublicEvent(
                project_id=row.project_id,
                sequence=row.sequence,
                event_type=row.event_type,
                topic=topic,
                phase_before=row.phase_before,
                phase_after=row.phase_after,
                payload=row.payload,
                occurred_at=_as_utc(row.occurred_at),
            )
            for row, topic in rows
        ]

    async def latest_sequence(self, project_id: str) -> int:
        latest = await self._db.scalar(
            select(func.max(SessionEventRow.sequence)).where(
                SessionEventRow.project_id == project_id
            )
        )
        return int(latest or 0)


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
