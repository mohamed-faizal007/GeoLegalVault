"""documents module router."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.db import get_db
from app.core.rbac import DOCUMENT_UPLOAD, DOCUMENT_VIEW, require
from app.modules.documents import service
from app.modules.documents.schemas import (
    DocumentListOut,
    DocumentOut,
    DownloadResponse,
    UploadResponse,
)
from app.modules.versions import service as versions_service
from app.services.geofence import require_geofence
from app.services.storage import generate_presigned_get

router = APIRouter(prefix="/documents", tags=["documents"])

_require_upload = require(DOCUMENT_UPLOAD)
_require_view = require(DOCUMENT_VIEW)
_require_upload_geofence = require_geofence("document_upload")
_require_download_geofence = require_geofence("document_download")


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(_require_upload)],
    _fence: Annotated[dict, Depends(_require_upload_geofence)],
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form()],
    doc_type: Annotated[str, Form()],
    classification: Annotated[str, Form()],
    tags: Annotated[str, Form()] = "",
) -> UploadResponse:
    data = await file.read()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    try:
        result = await service.create_document_with_v1(
            db,
            title=title,
            doc_type=doc_type,
            classification=classification,
            tags=tag_list,
            owner_id=user["_id"],
            data=data,
            content_type=file.content_type or "application/octet-stream",
        )
    finally:
        await file.close()

    return UploadResponse(
        document_id=str(result["document"]["_id"]),
        version_id=str(result["version"]["_id"]),
        sha256=result["version"]["sha256"],
        status=result["document"]["status"],
    )


@router.get("", response_model=DocumentListOut)
async def list_documents(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _actor: Annotated[dict, Depends(_require_view)],
    query: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    doc_type: str | None = None,
    owner: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DocumentListOut:
    items, total = await service.list_documents(
        db,
        query=query,
        status=status_filter,
        doc_type=doc_type,
        owner_id=owner,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )
    return DocumentListOut(
        items=[service.to_out(doc) for doc in items], page=page, limit=limit, total=total
    )


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _actor: Annotated[dict, Depends(_require_view)],
) -> DocumentOut:
    doc = await service.get_document_by_id(db, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")
    return service.to_out(doc)


@router.get("/{document_id}/download", response_model=DownloadResponse)
async def download_document(
    document_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _actor: Annotated[dict, Depends(_require_view)],
    _fence: Annotated[dict, Depends(_require_download_geofence)],
) -> DownloadResponse:
    doc = await service.get_document_by_id(db, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")
    if doc.get("current_version_id") is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Document has no version to download"
        )

    version = await versions_service.get_version_by_id(db, str(doc["current_version_id"]))
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Current version not found")

    settings = get_settings()
    url = generate_presigned_get(version["storage_key"])
    return DownloadResponse(url=url, expires_in_sec=settings.STORAGE_PRESIGN_TTL_SEC)
