"""Canonical JSON and Markdown journal exports."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, PlainTextResponse

from research_mentor.api.dependencies import get_container
from research_mentor.bootstrap import ApplicationContainer


router = APIRouter(prefix="/projects/{project_id}", tags=["exports"])


@router.get("/journal.json", response_class=JSONResponse)
async def journal_json(project_id: str, container: ApplicationContainer = Depends(get_container)):
    journal = await container.export_service.build(project_id)
    return JSONResponse(journal.model_dump(mode="json"))


@router.get("/journal.md", response_class=PlainTextResponse)
async def journal_markdown(project_id: str, container: ApplicationContainer = Depends(get_container)):
    journal = await container.export_service.build(project_id)
    return PlainTextResponse(container.journal_renderer.to_markdown(journal), media_type="text/markdown")
