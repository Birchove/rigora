"""Project domain models."""

from datetime import datetime

from pydantic import BaseModel, Field


class ResearchProject(BaseModel):
    project_id: str
    title: str
    domain: str
    session_id: str
    version: int = Field(ge=1)
    is_demo: bool = False
    created_at: datetime
    updated_at: datetime
