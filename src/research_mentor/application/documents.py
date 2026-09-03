"""Document upload lifecycle and durable parse jobs."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from pathlib import Path, PurePath
from uuid import uuid4

from research_mentor.adapters.documents.anydoc import AnydocParser
from research_mentor.adapters.documents.chunking import MarkdownChunker
from research_mentor.adapters.documents.plain_text import PlainTextParser, SUPPORTED_MEDIA_TYPES
from research_mentor.domain.documents import DocumentParseJob, UploadedDocument
from research_mentor.harness.state import SessionEvent, SessionEventType
from research_mentor.hyperparameters import DOCUMENT_PARSE_STALE_SECONDS
from research_mentor.ports.events import OutboxEvent
from research_mentor.ports.files import FileStorePort, StoredFile


class DocumentError(Exception):
    code = "document_error"
    status_code = 422


class DocumentNotFound(DocumentError):
    code = "document_not_found"
    status_code = 404


class UnsupportedDocument(DocumentError):
    code = "unsupported_document"


class DocumentQuotaExceeded(DocumentError):
    code = "document_quota_exceeded"
    status_code = 413


class DocumentStateConflict(DocumentError):
    code = "document_state_conflict"
    status_code = 409


class DocumentInUse(DocumentStateConflict):
    code = "document_in_use"


class DocumentService:
    def __init__(
        self,
        uow_factory,
        file_store: FileStorePort,
        *,
        allowed_media_types: tuple[str, ...],
        allowed_extensions: tuple[str, ...],
        max_file_bytes: int,
        max_project_bytes: int,
        chunk_max_chars: int,
        chunk_overlap_chars: int,
        new_id: Callable[[], str] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._file_store = file_store
        self._allowed_media_types = set(allowed_media_types)
        self._allowed_extensions = {item.casefold() for item in allowed_extensions}
        self._max_file_bytes = max_file_bytes
        self._max_project_bytes = max_project_bytes
        self._chunker = MarkdownChunker(max_chars=chunk_max_chars, overlap_chars=chunk_overlap_chars)
        self._new_id = new_id or (lambda: str(uuid4()))
        self._now = now or (lambda: datetime.now(timezone.utc))

    def _validate_upload(self, name: str, media_type: str) -> None:
        if not name or PurePath(name).name != name or "/" in name or "\\" in name:
            raise UnsupportedDocument("unsafe document name")
        if Path(name).suffix.casefold() not in self._allowed_extensions:
            raise UnsupportedDocument("unsupported extension")
        if media_type not in self._allowed_media_types:
            raise UnsupportedDocument("unsupported media type")

    async def upload(
        self, project_id: str, *, name: str, media_type: str, content: AsyncIterator[bytes]
    ) -> UploadedDocument:
        self._validate_upload(name, media_type)
        async with self._uow_factory() as uow:
            if await uow.projects.get(project_id) is None:
                raise DocumentNotFound("project not found")
            remaining = self._max_project_bytes - await uow.documents.total_size(project_id)
        limit = min(self._max_file_bytes, remaining)
        if limit <= 0:
            raise DocumentQuotaExceeded("project quota exceeded")

        seen = 0

        async def limited() -> AsyncIterator[bytes]:
            nonlocal seen
            async for chunk in content:
                seen += len(chunk)
                if seen > limit:
                    raise DocumentQuotaExceeded("upload quota exceeded")
                yield chunk

        document_id = self._new_id()
        stored = await self._file_store.put(project_id, document_id, limited())
        created_at = self._now()
        document = UploadedDocument(
            document_id=document_id, project_id=project_id, original_name=name,
            media_type=media_type, size_bytes=stored.size_bytes, sha256=stored.sha256,
            status="uploaded", created_at=created_at,
        )
        job = DocumentParseJob(
            job_id=self._new_id(), document_id=document_id, project_id=project_id,
            status="queued", attempt=1, created_at=created_at,
        )
        try:
            async with self._uow_factory() as uow:
                await uow.documents.add(document, storage_path=str(stored.path))
                await uow.document_parse_jobs.add(job)
        except BaseException:
            await self._file_store.remove(stored)
            raise
        return document

    async def list(self, project_id: str) -> list[UploadedDocument]:
        async with self._uow_factory() as uow:
            if await uow.projects.get(project_id) is None:
                raise DocumentNotFound("project not found")
            return await uow.documents.list(project_id)

    async def get(self, project_id: str, document_id: str) -> UploadedDocument:
        async with self._uow_factory() as uow:
            document = await uow.documents.get(document_id, project_id=project_id)
        if document is None:
            raise DocumentNotFound("document not found")
        return document

    async def retry(self, project_id: str, document_id: str) -> UploadedDocument:
        async with self._uow_factory() as uow:
            document = await uow.documents.get(document_id, project_id=project_id)
            if document is None:
                raise DocumentNotFound("document not found")
            if document.status != "failed":
                raise DocumentStateConflict("only failed documents can retry")
            attempt = await uow.document_parse_jobs.next_attempt(document_id)
            await uow.document_parse_jobs.add(DocumentParseJob(
                job_id=self._new_id(), document_id=document_id, project_id=project_id,
                status="queued", attempt=attempt, created_at=self._now(),
            ))
            await uow.documents.set_status(document_id, project_id=project_id, status="uploaded")
        return document.model_copy(update={"status": "uploaded", "error_message": None})

    @staticmethod
    def _referenced(session, document_id: str) -> bool:
        forward = session.research_context.forward_context if session.research_context else None
        if forward and document_id in forward.source_document_ids:
            return True
        results = [session.main_experiment, *session.completed_validations]
        return any(result and document_id in result.evidence_files for result in results)

    async def delete(self, project_id: str, document_id: str) -> None:
        async with self._uow_factory() as uow:
            project = await uow.projects.get(project_id)
            document = await uow.documents.get(document_id, project_id=project_id)
            if project is None or document is None:
                raise DocumentNotFound("document not found")
            session = await uow.sessions.get(project.session_id)
            if session is not None and self._referenced(session, document_id):
                raise DocumentInUse("document is referenced")
            storage_path = await uow.documents.storage_path(document_id, project_id=project_id)
            await uow.documents.delete(document_id, project_id=project_id)
        if storage_path:
            await self._file_store.remove(StoredFile(
                project_id=project_id, document_id=document_id, path=Path(storage_path),
                size_bytes=document.size_bytes, sha256=document.sha256,
            ))

    async def _emit_parse_progress(
        self,
        uow,
        *,
        job: DocumentParseJob,
        status: str,
        progress: float,
    ) -> None:
        project = await uow.projects.get(job.project_id)
        if project is None:
            return
        session = await uow.sessions.get(project.session_id)
        if session is None:
            return
        event_id = self._new_id()
        occurred_at = self._now()
        payload = {
            "document_id": job.document_id,
            "job_id": job.job_id,
            "status": status,
            "progress": progress,
        }
        await uow.events.append(
            SessionEvent(
                event_id=event_id,
                session_id=session.session_id,
                event_type=SessionEventType.DOCUMENT_PARSING_PROGRESS,
                phase_before=session.phase,
                phase_after=session.phase,
                payload=payload,
                occurred_at=occurred_at.isoformat(),
            )
        )
        await uow.outbox.append(
            OutboxEvent(
                outbox_id=self._new_id(),
                session_event_id=event_id,
                project_id=job.project_id,
                topic="document.parsing_progress",
                payload=payload,
                created_at=occurred_at,
            )
        )

    async def process(self, job_id: str) -> DocumentParseJob:
        async with self._uow_factory() as uow:
            job = await uow.document_parse_jobs.get(job_id)
            if job is None:
                raise DocumentNotFound("parse job not found")
            document = await uow.documents.get(job.document_id, project_id=job.project_id)
            storage_path = await uow.documents.storage_path(job.document_id, project_id=job.project_id)
            if document is None or storage_path is None:
                raise DocumentNotFound("document not found")
            started = self._now()
            job = job.model_copy(update={"status": "running", "started_at": started})
            await uow.document_parse_jobs.save(job)
            await uow.documents.set_status(job.document_id, project_id=job.project_id, status="parsing")
            await self._emit_parse_progress(uow, job=job, status="parsing", progress=0)
        stored = StoredFile(project_id=job.project_id, document_id=job.document_id,
                            path=Path(storage_path), size_bytes=document.size_bytes, sha256=document.sha256)
        parser = PlainTextParser() if document.media_type in SUPPORTED_MEDIA_TYPES else AnydocParser()
        try:
            parsed = await parser.parse(stored, document.media_type)
            chunks = self._chunker.split(document.document_id, parsed.markdown)
        except Exception:
            finished = self._now()
            failed = job.model_copy(update={"status": "failed", "finished_at": finished,
                                            "error_message": "document parsing failed"})
            async with self._uow_factory() as uow:
                await uow.document_parse_jobs.save(failed)
                await uow.documents.set_status(document.document_id, project_id=document.project_id,
                                               status="failed", error_message="document parsing failed")
                await self._emit_parse_progress(uow, job=failed, status="failed", progress=1)
            return failed
        finished = self._now()
        succeeded = job.model_copy(update={"status": "succeeded", "finished_at": finished})
        async with self._uow_factory() as uow:
            await uow.documents.replace_chunks(document.document_id, chunks)
            await uow.document_parse_jobs.save(succeeded)
            await uow.documents.set_status(document.document_id, project_id=document.project_id,
                                           status="ready", error_message=None)
            await self._emit_parse_progress(uow, job=succeeded, status="ready", progress=1)
        return succeeded


class DocumentParseWorker:
    def __init__(
        self,
        uow_factory,
        document_service: DocumentService,
        *,
        poll_interval: float = 0.25,
        stale_after_seconds: float = DOCUMENT_PARSE_STALE_SECONDS,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        if stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")
        self._uow_factory = uow_factory
        self._document_service = document_service
        self._poll_interval = poll_interval
        self._stale_after_seconds = stale_after_seconds
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._polling_task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        return self._polling_task is not None and not self._polling_task.done()

    async def start(self) -> None:
        if self.is_running:
            return
        self._polling_task = asyncio.create_task(self._poll())

    async def stop(self) -> None:
        task = self._polling_task
        self._polling_task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def drain_once(self) -> str | None:
        async with self._uow_factory() as uow:
            await uow.document_parse_jobs.requeue_stale_running(
                now=self._now(),
                stale_after_seconds=self._stale_after_seconds,
            )
            job = await uow.document_parse_jobs.next_queued()
        if job is None:
            return None
        await self._document_service.process(job.job_id)
        return job.job_id

    async def _poll(self) -> None:
        while True:
            job_id = await self.drain_once()
            if job_id is None:
                await asyncio.sleep(self._poll_interval)
