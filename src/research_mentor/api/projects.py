"""Project HTTP endpoints."""

from fastapi import APIRouter, Depends, status

from research_mentor.api.dependencies import get_container
from research_mentor.api.schemas import CreateProjectRequest, ErrorEnvelope
from research_mentor.application.views import ProjectView, ProjectViewService
from research_mentor.bootstrap import ApplicationContainer


router = APIRouter(prefix="/projects", tags=["projects"])
ERROR_RESPONSES = {
    404: {"model": ErrorEnvelope},
    409: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
    503: {"model": ErrorEnvelope},
}


def _service(container: ApplicationContainer) -> ProjectViewService:
    return ProjectViewService(container.uow_factory)


@router.post(
    "",
    response_model=ProjectView,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def create_project(
    body: CreateProjectRequest,
    container: ApplicationContainer = Depends(get_container),
) -> ProjectView:
    return await _service(container).create(title=body.title, domain=body.domain)


@router.get("", response_model=list[ProjectView], responses=ERROR_RESPONSES)
async def list_projects(
    container: ApplicationContainer = Depends(get_container),
) -> list[ProjectView]:
    return await _service(container).list()


@router.get("/{project_id}", response_model=ProjectView, responses=ERROR_RESPONSES)
async def get_project(
    project_id: str,
    container: ApplicationContainer = Depends(get_container),
) -> ProjectView:
    return await _service(container).get(project_id)
