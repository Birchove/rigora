"""Application composition root."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from research_mentor.adapters.memory.model import MemoryModelAdapter
from research_mentor.adapters.model.openai_compatible import (
    OpenAICompatibleModelAdapter,
)
from research_mentor.adapters.model.openai_responses import (
    OpenAIResponsesModelAdapter,
)
from research_mentor.adapters.sql.session import create_engine, create_session_factory
from research_mentor.adapters.sql.uow import SqlUnitOfWork
from research_mentor.application.command_bus import CommandBus
from research_mentor.application.handlers import CancelRunHandler, RestartResearchHandler
from research_mentor.application.recovery import RunRecovery
from research_mentor.application.run_worker import AgentRunWorker, RunService
from research_mentor.config import Settings
from research_mentor.ports.model import StructuredModelPort


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
    _provider_close: Callable[[], Awaitable[Any]] | None = None

    async def close_provider(self) -> None:
        if self._provider_close is not None:
            await self._provider_close()


def _build_model(
    settings: Settings,
) -> tuple[StructuredModelPort, Callable[[], Awaitable[Any]] | None]:
    if settings.model_provider == "demo":
        return MemoryModelAdapter(), None

    api_key = (
        settings.model_api_key.get_secret_value()
        if settings.model_api_key is not None
        else None
    )
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
            handlers={
                "cancel_run": CancelRunHandler(),
                "restart_research": RestartResearchHandler(),
            },
        )
        run_service = RunService(uow_factory)
        worker = AgentRunWorker(
            uow_factory,
            handlers={},
            worker_id=f"api-{uuid4()}",
            lease_seconds=settings.run_lease_seconds,
            lease_renewal_seconds=settings.run_lease_renewal_seconds,
            run_timeout=settings.run_timeout_seconds,
            retry_limit=settings.run_retry_limit,
        )
        recovery = RunRecovery(uow_factory)
        return ApplicationContainer(
            settings=settings,
            engine=engine,
            session_factory=session_factory,
            uow_factory=uow_factory,
            model=model,
            command_bus=command_bus,
            run_service=run_service,
            worker=worker,
            recovery=recovery,
            _provider_close=provider_close,
        )
    except BaseException:
        if provider_close is not None:
            await provider_close()
        await engine.dispose()
        raise
