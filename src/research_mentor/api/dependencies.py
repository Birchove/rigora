"""FastAPI dependencies backed by the application composition root."""

from fastapi import Request

from research_mentor.bootstrap import ApplicationContainer
from research_mentor.config import Settings


def get_container(request: Request) -> ApplicationContainer:
    return request.app.state.container


def get_settings(request: Request) -> Settings:
    return request.app.state.settings
