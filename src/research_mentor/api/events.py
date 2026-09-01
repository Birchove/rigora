"""Public Server-Sent Events endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse

from research_mentor.api.dependencies import get_container
from research_mentor.api.errors import ApiContractError
from research_mentor.application.event_stream import EventStreamService
from research_mentor.bootstrap import ApplicationContainer


router = APIRouter(prefix="/projects", tags=["events"])


def _cursor(after: int, last_event_id: str | None) -> int:
    if last_event_id is None:
        return after
    try:
        header_cursor = int(last_event_id)
    except ValueError as exc:
        raise ApiContractError(
            status_code=422,
            code="validation_error",
            message="Last-Event-ID 必须是非负整数。",
        ) from exc
    if header_cursor < 0:
        raise ApiContractError(
            status_code=422,
            code="validation_error",
            message="Last-Event-ID 必须是非负整数。",
        )
    return max(after, header_cursor)


@router.get("/{project_id}/events", response_class=StreamingResponse)
async def project_events(
    project_id: str,
    request: Request,
    after: Annotated[int, Query(ge=0)] = 0,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    container: ApplicationContainer = Depends(get_container),
) -> StreamingResponse:
    service = EventStreamService(container.uow_factory)
    cursor = _cursor(after, last_event_id)
    await service.ensure_project(project_id)
    return StreamingResponse(
        service.stream(
            project_id,
            after=cursor,
            disconnected=request.is_disconnected,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
