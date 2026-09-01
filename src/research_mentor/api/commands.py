"""Typed project command endpoint."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from research_mentor.api.dependencies import get_container, get_settings
from research_mentor.api.errors import ApiContractError
from research_mentor.api.projects import ERROR_RESPONSES
from research_mentor.api.schemas import AgentCommandResponse
from research_mentor.application.commands import AgentCommandReceipt, Command
from research_mentor.application.views import ProjectView, ProjectViewService
from research_mentor.bootstrap import ApplicationContainer
from research_mentor.config import Settings


router = APIRouter(prefix="/projects", tags=["commands"])


@router.post(
    "/{project_id}/commands",
    response_model=ProjectView,
    responses={
        202: {"model": AgentCommandResponse},
        **ERROR_RESPONSES,
    },
)
async def dispatch_command(
    project_id: str,
    command: Command,
    container: ApplicationContainer = Depends(get_container),
    settings: Settings = Depends(get_settings),
):
    if command.project_id != project_id:
        raise ApiContractError(
            status_code=422,
            code="project_id_mismatch",
            message="path project_id 与 command project_id 必须一致。",
        )
    result = await container.command_bus.dispatch(command)
    if isinstance(result, AgentCommandReceipt):
        return JSONResponse(
            status_code=202,
            content={"command_id": result.command_id, "run_id": result.run_id},
        )
    service = ProjectViewService(
        container.uow_factory,
        supported_domains=settings.supported_domains,
        supported_domain_aliases=settings.supported_domain_aliases,
    )
    return await service.get(project_id)
