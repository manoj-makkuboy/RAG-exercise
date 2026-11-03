from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, status

from app.ingest.parsers import EmptyDocument, UnsupportedFileType
from app.ingest.service import FileTooLarge
from app.models import DocumentOut

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(request: Request) -> list[DocumentOut]:
    return request.app.state.store.list_documents()


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(request: Request, response: Response, file: UploadFile) -> DocumentOut:
    max_bytes = request.app.state.settings.max_upload_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)  # read one extra byte to detect oversize cheaply
    try:
        doc, created = request.app.state.ingestion.ingest(file.filename or "upload", data)
    except FileTooLarge as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)) from exc
    except UnsupportedFileType as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    except EmptyDocument as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(request: Request, document_id: UUID) -> None:
    if not request.app.state.store.delete_document(document_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
