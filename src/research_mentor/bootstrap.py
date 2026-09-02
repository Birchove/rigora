"""Application composition root."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4
import logging

import httpx
from openai import AsyncOpenAI
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from research_mentor.adapters.demo.model import DemoModelAdapter
from research_mentor.adapters.demo.retrieval import DemoRetrievalAdapter
from research_mentor.adapters.openalex.client import OpenAlexRetriever
from research_mentor.adapters.model.openai_compatible import (
    OpenAICompatibleModelAdapter,
)
from research_mentor.adapters.model.openai_responses import (
    OpenAIResponsesModelAdapter,
)
from research_mentor.adapters.model.routing import RoutingModelAdapter
from research_mentor.adapters.sql.session import create_engine, create_session_factory
from research_mentor.adapters.sql.uow import SqlUnitOfWork
from research_mentor.application.command_bus import CommandBus
from research_mentor.application.production import build_command_handlers, build_run_handlers
from research_mentor.application.recovery import RunRecovery
from research_mentor.application.run_worker import AgentRunWorker, RunService
from research_mentor.application.documents import DocumentService
from research_mentor.application.journal import ExportService, JournalRenderer
from research_mentor.application.demo import DemoService
from research_mentor.adapters.filestore.local import LocalFileStore
from research_mentor.config import SHARED_AGENTS, SLOTS, Settings, SlotName
from research_mentor.ports.model import StructuredModelPort


logger = logging.getLogger("research_mentor.runs")

# 国内网关走系统 HTTP 代理时经常读超时；这些 host 直连。
_DIRECT_CONNECT_MARKERS = (
    "wanjiedata.com",
    "dashscope.aliyuncs.com",
    "bigmodel.cn",
)


def _direct_connect(base_url: str) -> bool:
    return any(marker in base_url for marker in _DIRECT_CONNECT_MARKERS)


UowFactory = Callable[[], SqlUnitOfWork]


@dataclass(slots=True)
class ApplicationContainer:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    uow_factory: UowFactory
    model: StructuredModelPort
    command_bus: CommandBus
    run_service: RunService
    worker: AgentRunWorker
    recovery: RunRecovery
    document_service: DocumentService
    export_service: ExportService
    journal_renderer: JournalRenderer
    demo_service: DemoService
    _provider_close: Callable[[], Awaitable[Any]] | None = None

    async def close_provider(self) -> None:
        if self._provider_close is not None:
            await self._provider_close()


def _use_openalex(settings: Settings) -> bool:
    if any(getattr(settings, f"{slot}_agents") for slot in SLOTS):
        return True
    return settings.model_provider != "demo"


def _usable_secret(secret: SecretStr | None) -> str | None:
    if secret is None:
        return None
    raw = secret.get_secret_value().strip()
    return raw or None


def _build_vendor_adapter(
    settings: Settings,
    slot: SlotName,
) -> tuple[StructuredModelPort, Callable[[], Awaitable[Any]] | None]:
    api_key = _usable_secret(settings.slot_api_key(slot))
    api_style = settings.slot_api_style(slot)
    base_url = settings.slot_base_url(slot)
    if api_style == "responses":
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        return OpenAIResponsesModelAdapter(client), client.close
    if not base_url:
        raise ValueError(f"{slot} chat_completions requires base_url")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    direct = _direct_connect(base_url)
    if direct:
        logger.info("model http client direct-connect host=%s", base_url)
    client = httpx.AsyncClient(headers=headers, trust_env=not direct)
    # chat_completions 中转普遍不支持 json_schema，卡住会变成空超时。
    return (
        OpenAICompatibleModelAdapter(
            client,
            base_url=base_url,
            response_format_mode="json_object",
        ),
        client.aclose,
    )


def _build_model(
    settings: Settings,
) -> tuple[StructuredModelPort, Callable[[], Awaitable[Any]] | None]:
    routes: dict[str, StructuredModelPort] = {}
    closers: list[Callable[[], Awaitable[Any]]] = []
    for slot in SLOTS:
        agents = getattr(settings, f"{slot}_agents")
        if not agents:
            continue
        adapter, closer = _build_vendor_adapter(settings, slot)
        if closer is not None:
            closers.append(closer)
        routes[settings.slot_model(slot)] = adapter
        for agent in agents:
            if agent in SHARED_AGENTS:
                routes.setdefault(agent, adapter)
            else:
                routes[agent] = adapter
    if routes:

        async def close_all() -> None:
            for closer in closers:
                await closer()

        return RoutingModelAdapter(routes, fallback=DemoModelAdapter()), close_all

    if settings.model_provider == "demo":
        return DemoModelAdapter(), None

    api_key = _usable_secret(settings.model_api_key)
    if settings.model_provider == "openai":
        client = AsyncOpenAI(api_key=api_key)
        return OpenAIResponsesModelAdapter(client), client.close

    if settings.model_base_url is None:
        raise ValueError("openai_compatible requires model_base_url")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    client = httpx.AsyncClient(headers=headers)
    return (
        OpenAICompatibleModelAdapter(
            client,
            base_url=str(settings.model_base_url),
        ),
        client.aclose,
    )


async def build_container(settings: Settings) -> ApplicationContainer:
    model, provider_close = _build_model(settings)
    engine = create_engine(settings.database_url)
    try:
        session_factory = create_session_factory(engine)
        uow_factory = lambda: SqlUnitOfWork(session_factory)
        command_bus = CommandBus(
            uow_factory,
            handlers=build_command_handlers(model=model, settings=settings),
        )
        run_service = RunService(uow_factory)
        retriever: Any = DemoRetrievalAdapter()
        if _use_openalex(settings):
            logger.info(
                "literature retriever=OpenAlex demo_mode=%s keyed=%s",
                settings.demo_mode,
                bool(_usable_secret(settings.openalex_api_key)),
            )
            openalex_client = httpx.AsyncClient(timeout=30.0)
            retriever = OpenAlexRetriever(
                openalex_client,
                mailto=settings.openalex_mailto,
                api_key=_usable_secret(settings.openalex_api_key),
            )
            previous_close = provider_close

            async def close_with_openalex() -> None:
                if previous_close is not None:
                    await previous_close()
                await openalex_client.aclose()

            provider_close = close_with_openalex
        else:
            logger.info("literature retriever=demo (no vendor agents, model_provider=demo)")
        worker = AgentRunWorker(
            uow_factory,
            handlers=build_run_handlers(
                uow_factory, model=model, settings=settings, retriever=retriever
            ),
            worker_id=f"api-{uuid4()}",
            lease_seconds=settings.run_lease_seconds,
            lease_renewal_seconds=settings.run_lease_renewal_seconds,
            run_timeout=settings.run_timeout_seconds,
            retry_limit=settings.run_retry_limit,
        )
        recovery = RunRecovery(uow_factory)
        document_service = DocumentService(
            uow_factory,
            LocalFileStore(settings.upload_root),
            allowed_media_types=settings.upload_allowed_media_types,
            allowed_extensions=settings.upload_allowed_extensions,
            max_file_bytes=settings.upload_max_file_bytes,
            max_project_bytes=settings.upload_max_project_bytes,
            chunk_max_chars=settings.document_chunk_max_chars,
            chunk_overlap_chars=settings.document_chunk_overlap_chars,
        )
        export_service = ExportService(uow_factory)
        demo_service = DemoService(uow_factory, export_service)
        container = ApplicationContainer(
            settings=settings,
            engine=engine,
            session_factory=session_factory,
            uow_factory=uow_factory,
            model=model,
            command_bus=command_bus,
            run_service=run_service,
            worker=worker,
            recovery=recovery,
            document_service=document_service,
            export_service=export_service,
            journal_renderer=JournalRenderer(),
            demo_service=demo_service,
            _provider_close=provider_close,
        )
        if settings.demo_mode:
            await demo_service.ensure_seeded()
        return container
    except BaseException:
        if provider_close is not None:
            await provider_close()
        await engine.dispose()
        raise
