from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from research_mentor.adapters.filestore.local import LocalFileStore
from research_mentor.adapters.sql.base import Base
from research_mentor.adapters.sql.uow import SqlUnitOfWork
from research_mentor.application.documents import DocumentParseWorker, DocumentService
from research_mentor.application.journal import ExportService, JournalRenderer
from research_mentor.config import Settings
from research_mentor.domain.projects import ResearchProject
from research_mentor.domain.experiments import MainExperimentResult
from research_mentor.harness.state import ResearchSession


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


class _Noop:
    async def requeue_expired(self): return ()
    async def start(self): return None
    async def stop(self): return None


@dataclass
class _Container:
    settings: Settings
    engine: object
    uow_factory: object
    document_service: DocumentService
    export_service: ExportService
    journal_renderer: JournalRenderer
    recovery: object = _Noop()
    worker: object = _Noop()
    document_worker: object = _Noop()
    command_bus: object = None


@asynccontextmanager
async def _client(monkeypatch, tmp_path, *, file_limit=32, project_limit=64):
    from research_mentor.api import app as app_module
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'documents.db'}",
        upload_root=tmp_path / "uploads",
        upload_max_file_bytes=file_limit,
        upload_max_project_bytes=project_limit,
    )
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    uow_factory = lambda: SqlUnitOfWork(factory)
    async with uow_factory() as uow:
        await uow.projects.add(ResearchProject(
            project_id="p1", title="项目一", domain="computer_science", session_id="s1",
            version=1, created_at=NOW, updated_at=NOW,
        ))
        await uow.sessions.add(ResearchSession(session_id="s1"), project_id="p1")
        await uow.projects.add(ResearchProject(
            project_id="p2", title="项目二", domain="computer_science", session_id="s2",
            version=1, created_at=NOW, updated_at=NOW,
        ))
        await uow.sessions.add(ResearchSession(session_id="s2"), project_id="p2")
    service = DocumentService(
        uow_factory, LocalFileStore(settings.upload_root),
        allowed_media_types=settings.upload_allowed_media_types,
        allowed_extensions=settings.upload_allowed_extensions,
        max_file_bytes=settings.upload_max_file_bytes,
        max_project_bytes=settings.upload_max_project_bytes,
        chunk_max_chars=settings.document_chunk_max_chars,
        chunk_overlap_chars=settings.document_chunk_overlap_chars,
    )
    container = _Container(settings, engine, uow_factory, service,
                           ExportService(uow_factory), JournalRenderer())
    async def fake_build_container(received): return container
    monkeypatch.setattr(app_module, "build_container", fake_build_container)
    app = app_module.create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                     base_url="http://test") as client:
            yield client, container


@pytest.mark.anyio
async def test_upload_list_get_and_project_isolation(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path) as (client, _):
        uploaded = await client.post("/api/v1/projects/p1/documents",
                                     files={"file": ("notes.md", b"# Experiment", "text/markdown")})
        assert uploaded.status_code == 202
        body = uploaded.json()
        assert body["status"] == "uploaded"
        assert len(body["sha256"]) == 64
        assert (await client.get("/api/v1/projects/p1/documents")).json() == [body]
        assert (await client.get(f"/api/v1/projects/p2/documents/{body['document_id']}")).status_code == 404


@pytest.mark.anyio
async def test_parse_worker_drains_queued_markdown_to_ready(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path) as (client, container):
        body = (await client.post(
            "/api/v1/projects/p1/documents",
            files={"file": ("notes.md", "# Experiment\n\nlayer-wise KV.".encode(), "text/markdown")},
        )).json()
        assert body["status"] == "uploaded"
        worker = DocumentParseWorker(container.uow_factory, container.document_service)
        job_id = await worker.drain_once()
        assert job_id is not None
        document = await container.document_service.get("p1", body["document_id"])
        assert document.status == "ready"
        assert await worker.drain_once() is None
        async with container.uow_factory() as uow:
            events = await uow.events.list_for_project_after("p1", after=0)
        payloads = [event.payload for event in events if event.topic == "document.parsing_progress"]
        assert [item["status"] for item in payloads] == ["parsing", "ready"]


@pytest.mark.anyio
async def test_stale_running_parse_job_is_requeued(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path) as (client, container):
        body = (await client.post(
            "/api/v1/projects/p1/documents",
            files={"file": ("notes.md", b"# Experiment", "text/markdown")},
        )).json()
        stale_started = datetime.now(timezone.utc) - timedelta(minutes=20)
        async with container.uow_factory() as uow:
            job = await uow.document_parse_jobs.latest_for_document(body["document_id"])
            assert job is not None
            await uow.document_parse_jobs.save(job.model_copy(update={
                "status": "running",
                "started_at": stale_started,
            }))
            await uow.documents.set_status(
                body["document_id"], project_id="p1", status="parsing"
            )
        worker = DocumentParseWorker(
            container.uow_factory,
            container.document_service,
            stale_after_seconds=60,
        )
        assert await worker.drain_once() == job.job_id
        document = await container.document_service.get("p1", body["document_id"])
        assert document.status == "ready"


@pytest.mark.anyio
async def test_upload_rejects_quota_mime_and_traversal_and_cleans_blob(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path, file_limit=8, project_limit=8) as (client, _):
        oversized = await client.post("/api/v1/projects/p1/documents",
                                       files={"file": ("large.md", b"123456789", "text/markdown")})
        wrong_mime = await client.post("/api/v1/projects/p1/documents",
                                        files={"file": ("note.md", b"ok", "image/png")})
        traversal = await client.post("/api/v1/projects/p1/documents",
                                       files={"file": ("../note.md", b"ok", "text/markdown")})
        assert oversized.status_code == 413
        assert wrong_mime.json()["error"]["code"] == "unsupported_document"
        assert traversal.json()["error"]["code"] == "unsupported_document"
        assert list((tmp_path / "uploads").rglob("source.bin")) == []


@pytest.mark.anyio
async def test_failed_retry_new_attempt_and_delete_rules(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path) as (client, container):
        body = (await client.post("/api/v1/projects/p1/documents",
                    files={"file": ("notes.md", b"text", "text/markdown")})).json()
        document_id = body["document_id"]
        async with container.uow_factory() as uow:
            await uow.documents.set_status(document_id, project_id="p1", status="failed", error_message="bad")
        retried = await client.post(f"/api/v1/projects/p1/documents/{document_id}/retry")
        assert retried.status_code == 202 and retried.json()["status"] == "uploaded"
        async with container.uow_factory() as uow:
            assert await uow.document_parse_jobs.next_attempt(document_id) == 3
            project = await uow.projects.get("p1")
            session = await uow.sessions.get(project.session_id)
            session = session.model_copy(update={"main_experiment": MainExperimentResult(
                objective="比较", method="实验", actual_result="结果", conclusion="结论",
                execution_status="completed", impact="supports", evidence_files=[document_id],
            )})
            await uow.sessions.save(session, expected_version=1)
        referenced = await client.delete(f"/api/v1/projects/p1/documents/{document_id}")
        assert referenced.status_code == 409
        assert referenced.json()["error"]["code"] == "document_in_use"
        async with container.uow_factory() as uow:
            project = await uow.projects.get("p1")
            session = await uow.sessions.get(project.session_id)
            await uow.sessions.save(session.model_copy(update={"main_experiment": None}), expected_version=2)
        assert (await client.delete(f"/api/v1/projects/p1/documents/{document_id}")).status_code == 204


@pytest.mark.anyio
async def test_parse_job_is_durable_and_failed_parse_keeps_source(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path) as (client, container):
        body = (await client.post("/api/v1/projects/p1/documents",
                    files={"file": ("bad.txt", b"\xff", "text/plain")})).json()
        async with container.uow_factory() as uow:
            queued = await uow.document_parse_jobs.latest_for_document(body["document_id"])
        failed = await container.document_service.process(queued.job_id)
        assert failed.status == "failed" and failed.attempt == 1
        document = await container.document_service.get("p1", body["document_id"])
        assert document.status == "failed"
        assert list((tmp_path / "uploads").rglob("source.bin"))
        assert (await client.post(
            f"/api/v1/projects/p1/documents/{body['document_id']}/retry"
        )).status_code == 202


@pytest.mark.anyio
async def test_journal_endpoints_share_canonical_model(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path) as (client, _):
        json_response = await client.get("/api/v1/projects/p1/journal.json")
        markdown_response = await client.get("/api/v1/projects/p1/journal.md")
        assert json_response.status_code == markdown_response.status_code == 200
        assert json_response.json()["project"]["project_id"] == "p1"
        assert "## 实验结果" in markdown_response.text
        assert "EvidenceRef" not in markdown_response.text
