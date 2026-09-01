import asyncio

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from research_mentor.adapters.demo.model import DemoModelAdapter
from research_mentor.adapters.demo.retrieval import DemoRetrievalAdapter
from research_mentor.adapters.sql.base import Base
from research_mentor.adapters.sql.uow import SqlUnitOfWork
from research_mentor.agents.complete.contracts import CompleteAgentOutput
from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.application.demo import DEMO_EVENT_SCRIPT, DemoService
from research_mentor.application.journal import ExportService
from research_mentor.application.views import ProjectViewService
from research_mentor.config import Settings
from research_mentor.harness.phase import SessionPhase
from research_mentor.ports.model import ModelRequest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def demo_context(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'demo.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    uow_factory = lambda: SqlUnitOfWork(factory)
    service = DemoService(uow_factory, ExportService(uow_factory))
    yield service, uow_factory
    await engine.dispose()


@pytest.mark.anyio
async def test_demo_seed_creates_three_real_schema_projects(demo_context):
    service, _ = demo_context

    projects = await service.ensure_seeded()

    assert [item.demo_stage for item in projects] == [
        "submitted_idea",
        "working",
        "validation_selection",
    ]
    assert [item.phase for item in projects] == [
        SessionPhase.PLANNING,
        SessionPhase.WORKING,
        SessionPhase.AWAITING_VALIDATION_SELECTION,
    ]
    assert all(item.is_demo and item.visible_evidence for item in projects)
    validation = projects[2]
    assert CompleteAgentOutput.model_validate(validation.latest_complete_output)
    assert validation.validation_candidates
    assert (await service.export(validation.project_id, "json")).writing_guidance


@pytest.mark.anyio
async def test_demo_seed_is_idempotent_and_concurrent_safe(demo_context):
    service, _ = demo_context

    first, second = await asyncio.gather(service.ensure_seeded(), service.ensure_seeded())
    third = await service.ensure_seeded()

    expected = [item.project_id for item in first]
    assert [item.project_id for item in second] == expected
    assert [item.project_id for item in third] == expected


@pytest.mark.anyio
async def test_project_view_exposes_persisted_demo_marker(demo_context):
    service, uow_factory = demo_context
    await service.ensure_seeded()
    views = ProjectViewService(
        uow_factory,
        supported_domains=("computer_science",),
        supported_domain_aliases=("cs",),
        new_id=iter(("real-project", "real-session", "real-event", "real-outbox")).__next__,
    )

    real = await views.create(title="真实项目", domain="cs")
    seeded = await views.list()

    assert real.is_demo is False
    assert sum(item.is_demo for item in seeded) == 3


def test_demo_event_delays_and_payloads_are_public_and_deterministic():
    assert [item.delay_ms for item in DEMO_EVENT_SCRIPT] == [0, 120, 240, 360]
    assert all("prompt" not in item.payload for item in DEMO_EVENT_SCRIPT)


@pytest.mark.anyio
async def test_demo_adapters_return_production_schemas():
    model = DemoModelAdapter()
    result = await model.generate(
        ModelRequest(
            agent_name="idea_review",
            model_profile="demo",
            instructions="review",
            user_input="submit_idea",
            output_model=IdeaReviewOutput,
            timeout=1,
            trace_id="demo-trace",
        )
    )
    records = await DemoRetrievalAdapter().search("state compression", limit=2)

    assert isinstance(result, IdeaReviewOutput)
    assert records and all(item.provider == "demo" for item in records)
    assert all(item.url and item.url.startswith("demo://") for item in records)


@pytest.mark.anyio
async def test_bootstrap_seeds_only_when_demo_mode(tmp_path):
    from research_mentor.bootstrap import build_container

    async def project_count(container):
        async with container.uow_factory() as uow:
            return len(await uow.projects.list())

    for enabled, expected in ((True, 3), (False, 0)):
        database_url = f"sqlite+aiosqlite:///{tmp_path / f'{enabled}.db'}"
        engine = create_async_engine(database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()
        container = await build_container(
            Settings(model_provider="demo", demo_mode=enabled, database_url=database_url)
        )
        try:
            assert await project_count(container) == expected
        finally:
            await container.close_provider()
            await container.engine.dispose()
