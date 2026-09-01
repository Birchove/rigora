"""Project-isolated document HTTP endpoints."""

from fastapi import APIRouter, Depends, UploadFile, status

from research_mentor.api.dependencies import get_container
from research_mentor.api.schemas import ErrorEnvelope
from research_mentor.bootstrap import ApplicationContainer
from research_mentor.domain.documents import UploadedDocument


router = APIRouter(prefix="/projects/{project_id}/documents", tags=["documents"])
ERROR_RESPONSES = {
    404: {"model": ErrorEnvelope}, 409: {"model": ErrorEnvelope},
    413: {"model": ErrorEnvelope}, 422: {"model": ErrorEnvelope},
}


@router.post("", response_model=UploadedDocument, status_code=status.HTTP_202_ACCEPTED,
             responses=ERROR_RESPONSES)
async def upload_document(
    project_id: str, file: UploadFile,
    container: ApplicationContainer = Depends(get_container),
) -> UploadedDocument:
    async def chunks():
        while chunk := await file.read(64 * 1024):
            yield chunk
    try:
        return await container.document_service.upload(
            project_id, name=file.filename or "", media_type=file.content_type or "", content=chunks()
        )
    finally:
        await file.close()


@router.get("", response_model=list[UploadedDocument], responses=ERROR_RESPONSES)
async def list_documents(project_id: str, container: ApplicationContainer = Depends(get_container)):
    return await container.document_service.list(project_id)


@router.get("/{document_id}", response_model=UploadedDocument, responses=ERROR_RESPONSES)
async def get_document(project_id: str, document_id: str,
                       container: ApplicationContainer = Depends(get_container)):
    return await container.document_service.get(project_id, document_id)


@router.post("/{document_id}/retry", response_model=UploadedDocument,
             status_code=status.HTTP_202_ACCEPTED, responses=ERROR_RESPONSES)
async def retry_document(project_id: str, document_id: str,
                         container: ApplicationContainer = Depends(get_container)):
    return await container.document_service.retry(project_id, document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT,
               responses=ERROR_RESPONSES)
async def delete_document(project_id: str, document_id: str,
                          container: ApplicationContainer = Depends(get_container)) -> None:
    await container.document_service.delete(project_id, document_id)
