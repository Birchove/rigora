"""Recoverable, allowlisted public event stream."""

import asyncio
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from research_mentor.application.views import ProjectNotFoundError
from research_mentor.ports.events import PersistedPublicEvent


PUBLIC_EVENT_TYPES = {
    "command.accepted",
    "run.started",
    "run.completed",
    "run.failed",
    "retrieval.started",
    "retrieval.results",
    "retrieval.unavailable",
    "document.parsing_progress",
    "agent.stage",
    "session.phase_changed",
    "evidence.added",
    "user_input.required",
    "export.ready",
}

_INTERNAL_TYPE_MAP = {
    "session_created": "session.phase_changed",
    "idea_reviewed": "agent.stage",
    "plan_generated": "agent.stage",
    "key_insight_checked": "agent.stage",
    "plan_decided": "agent.stage",
    "working_started": "agent.stage",
    "working_turn_completed": "agent.stage",
    "working_resumed": "agent.stage",
    "result_recorded": "agent.stage",
    "complete_guidance_generated": "agent.stage",
    "validations_selected": "agent.stage",
    "plan_revision_decided": "agent.stage",
    "run_failed": "run.failed",
}

_PAYLOAD_FIELDS = {
    "command.accepted": {"command_id", "run_id", "command_type", "status"},
    "run.started": {"run_id", "agent_name", "status", "attempt", "public_message"},
    "run.completed": {"run_id", "agent_name", "status", "public_message"},
    "run.failed": {"run_id", "agent_name", "status", "error_code", "public_message"},
    "retrieval.started": {"query_id", "source", "status"},
    "retrieval.results": {"query_id", "source", "result_count", "status"},
    "retrieval.unavailable": {"query_id", "source", "status", "public_message"},
    "document.parsing_progress": {"document_id", "job_id", "status", "progress"},
    "agent.stage": {"agent_name", "stage", "status", "public_message"},
    "session.phase_changed": {"session_id", "phase_before", "phase_after"},
    "evidence.added": {"evidence_id", "source_type", "title"},
    "user_input.required": {"kind", "status", "public_message", "allowed_commands"},
    "export.ready": {"export_id", "format", "status", "download_url"},
}

_SENSITIVE_PARTS = (
    "prompt",
    "apikey",
    "secret",
    "chainofthought",
    "providerpayload",
    "rawmessage",
    "filecontent",
)


def _is_sensitive(key: str) -> bool:
    normalized = "".join(character for character in key.casefold() if character.isalnum())
    return any(part in normalized for part in _SENSITIVE_PARTS)


def _safe_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _safe_value(item)
            for key, item in value.items()
            if not _is_sensitive(str(key))
        }
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    return value


def _project(event: PersistedPublicEvent) -> tuple[str, dict[str, Any]] | None:
    public_type = (
        event.topic
        if event.topic in PUBLIC_EVENT_TYPES
        else event.event_type
        if event.event_type in PUBLIC_EVENT_TYPES
        else _INTERNAL_TYPE_MAP.get(event.event_type)
    )
    if public_type is None:
        return None
    allowed = _PAYLOAD_FIELDS[public_type]
    payload = {
        key: _safe_value(value)
        for key, value in event.payload.items()
        if key in allowed
        and not _is_sensitive(key)
    }
    if public_type == "session.phase_changed":
        payload.update(
            phase_before=event.phase_before,
            phase_after=event.phase_after,
        )
    elif public_type == "agent.stage":
        payload.setdefault("stage", event.event_type)
        payload.setdefault("status", "completed")
    return public_type, payload


def encode_sse(event: PersistedPublicEvent) -> str | None:
    projected = _project(event)
    if projected is None:
        return None
    public_type, payload = projected
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return f"id: {event.sequence}\nevent: {public_type}\ndata: {data}\n\n"


class EventStreamService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        *,
        poll_interval: float = 1.0,
        heartbeat_interval: float = 15.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._uow_factory = uow_factory
        self._poll_interval = poll_interval
        self._heartbeat_interval = heartbeat_interval
        self._sleep = sleep
        self._monotonic = monotonic

    async def ensure_project(self, project_id: str) -> None:
        async with self._uow_factory() as uow:
            if await uow.projects.get(project_id) is None:
                raise ProjectNotFoundError(project_id)

    async def stream(
        self,
        project_id: str,
        *,
        after: int,
        disconnected: Callable[[], Awaitable[bool]] | None = None,
        max_cycles: int | None = None,
    ) -> AsyncIterator[str]:
        cursor = after
        last_activity = self._monotonic()
        cycles = 0
        while max_cycles is None or cycles < max_cycles:
            if disconnected is not None and await disconnected():
                return
            async with self._uow_factory() as uow:
                events = await uow.events.list_for_project_after(
                    project_id, after=cursor
                )
            emitted = False
            seen: set[int] = set()
            for event in sorted(events, key=lambda item: item.sequence):
                if event.sequence <= cursor or event.sequence in seen:
                    continue
                seen.add(event.sequence)
                chunk = encode_sse(event)
                cursor = event.sequence
                if chunk is None:
                    continue
                emitted = True
                yield chunk
            now = self._monotonic()
            if emitted:
                last_activity = now
            elif now - last_activity >= self._heartbeat_interval:
                yield ": heartbeat\n\n"
                last_activity = now
            cycles += 1
            if max_cycles is None or cycles < max_cycles:
                await self._sleep(self._poll_interval)


__all__ = [
    "PUBLIC_EVENT_TYPES",
    "EventStreamService",
    "PersistedPublicEvent",
    "encode_sse",
]
