"""Public event publication boundary."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, JsonValue


class OutboxEvent(BaseModel):
    outbox_id: str
    session_event_id: str
    project_id: str
    topic: str
    payload: dict[str, JsonValue]
    created_at: datetime
    published_at: datetime | None = None


class PublicEventPublisherPort(Protocol):
    async def publish_pending(self, events: Sequence[OutboxEvent]) -> None: ...
