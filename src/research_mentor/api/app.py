"""FastAPI application factory and process lifecycle."""

from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI

from research_mentor.api.dependencies import get_settings
from research_mentor.api.commands import router as commands_router
from research_mentor.api.errors import install_error_handlers
from research_mentor.api.projects import router as projects_router
from research_mentor.api.documents import router as documents_router
from research_mentor.api.exports import router as exports_router
from research_mentor.api.events import router as events_router
from research_mentor.bootstrap import build_container
from research_mentor.config import Settings


api_router = APIRouter()


@api_router.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {
        "status": "ok",
        "database": "ok",
        "model_provider": settings.model_provider,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = None
    worker_start_attempted = False
    try:
        container = await build_container(app.state.settings)
        app.state.container = container
        await container.recovery.requeue_expired()
        worker_start_attempted = True
        await container.worker.start()
        yield
    finally:
        if container is not None:
            try:
                if worker_start_attempted:
                    await container.worker.stop()
                close_provider = getattr(container, "close_provider", None)
                if close_provider is not None:
                    await close_provider()
            finally:
                await container.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    application = FastAPI(
        title="Research Mentor API",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.settings = settings if settings is not None else Settings()
    application.include_router(api_router, prefix="/api/v1")
    application.include_router(projects_router, prefix="/api/v1")
    application.include_router(commands_router, prefix="/api/v1")
    application.include_router(documents_router, prefix="/api/v1")
    application.include_router(exports_router, prefix="/api/v1")
    application.include_router(events_router, prefix="/api/v1")
    install_error_handlers(application)
    return application
