"""documents module router."""

from datetime import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.db import get_db
from app.core.rbac import (
    APPROVE_PERFORM,
    DOCUMENT_AMEND,
    DOCUMENT_ARCHIVE,
    DOCUMENT_SUBMIT,
    DOCUMENT_UPLOAD,
    DOCUMENT_VIEW,
    REVIEW_PERFORM,
    RBACError,
    has_permission,
    require,
)
from app.modules.audit import service as audit
from app.modules.documents import service, workflow
from app.modules.documents.models import DocumentStatus
from app.modules.documents.schemas import (
    AmendRequest,
    DocumentListOut,
    DocumentOut,
    DownloadResponse,
    ReviewDecision,
    TransitionResponse,
    UploadResponse,
)
from app.modules.versions import service as versions_service
from app.services.geofence import require_geofence
from app.services.storage import generate_presigned_get

router = APIRouter(prefix="/documents", tags=["documents"])

_require_upload = require(DOCUMENT_UPLOAD)
_require_view = require(DOCUMENT_VIEW)
_require_submit = require(DOCUMENT_SUBMIT)
_require_review = require(REVIEW_PERFORM)
_require_approve = require(APPROVE_PERFORM)
_require_amend = require(DOCUMENT_AMEND)
_require_archive = require(DOCUMENT_ARCHIVE)
_require_upload_geofence = require_geofence("document_upload")
_require_download_geofence = require_geofence("document_download")
_require_approve_geofence = require_geofence("document_approve")
_require_amend_geofence = require_geofence("document_amend")


async def _get_document_or_404(db: AsyncIOMotorDatabase, document_id: str) -> dict:
    doc = await service.get_document_by_id(db, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(_require_upload)],
    _fence: Annotated[dict, Depends(_require_upload_geofence)],
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form()],
    doc_type: Annotated[str, Form()],
    classification: Annotated[str, Form()],
    tags: Annotated[str, Form()] = "",
    amend_of: Annotated[str | None, Form()] = None,
) -> UploadResponse:
    data = await file.read()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    content_type = file.content_type or "application/octet-stream"

    try:
        if amend_of:
            if not has_permission(user["role"], DOCUMENT_AMEND):
                raise RBACError("FORBIDDEN", f"Missing required permission: {DOCUMENT_AMEND}")
            document = await _get_document_or_404(db, amend_of)
            if document["status"] != DocumentStatus.AMENDMENT_REQUESTED.value:
                raise workflow.IllegalTransition(
                    "document must be AMENDMENT_REQUESTED to accept a new version "
                    f"(current status: {document['status']})"
                )
            result = await service.create_next_version(
                db,
                document=document,
                actor_id=user["_id"],
                data=data,
                content_type=content_type,
            )
        else:
            result = await service.create_document_with_v1(
                db,
                title=title,
                doc_type=doc_type,
                classification=classification,
                tags=tag_list,
                owner_id=user["_id"],
                data=data,
                content_type=content_type,
            )
    finally:
        await file.close()

    await audit.record(
        actor_id=user["_id"],
        action="UPLOAD",
        target_type="document",
        target_id=result["document"]["_id"],
        result="SUCCESS",
        ip=request.client.host if request.client else None,
        meta={
            "version_id": str(result["version"]["_id"]),
            "version_no": result["version"]["version_no"],
            "amend": bool(amend_of),
        },
    )
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
    doc = await _get_document_or_404(db, document_id)
    return service.to_out(doc)


@router.get("/{document_id}/download", response_model=DownloadResponse)
async def download_document(
    document_id: str,
    request: Request,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    actor: Annotated[dict, Depends(_require_view)],
    _fence: Annotated[dict, Depends(_require_download_geofence)],
) -> DownloadResponse:
    doc = await _get_document_or_404(db, document_id)
    if doc.get("current_version_id") is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Document has no version to download"
        )

    version = await versions_service.get_version_by_id(db, str(doc["current_version_id"]))
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Current version not found")

    settings = get_settings()
    url = generate_presigned_get(version["storage_key"])
    await audit.record(
        actor_id=actor["_id"],
        action="ACCESS",
        target_type="document",
        target_id=doc["_id"],
        result="SUCCESS",
        ip=request.client.host if request.client else None,
        meta={"version_id": str(version["_id"])},
    )
    return DownloadResponse(url=url, expires_in_sec=settings.STORAGE_PRESIGN_TTL_SEC)


@router.post("/{document_id}/submit", response_model=TransitionResponse)
async def submit_document(
    document_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(_require_submit)],
) -> TransitionResponse:
    document = await _get_document_or_404(db, document_id)
    updated = await workflow.submit(db, document=document, actor=user)
    return TransitionResponse(document_id=document_id, status=updated["status"])


@router.post("/{document_id}/review", response_model=TransitionResponse)
async def review_document(
    document_id: str,
    payload: ReviewDecision,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(_require_review)],
) -> TransitionResponse:
    document = await _get_document_or_404(db, document_id)
    updated = await workflow.review(
        db, document=document, actor=user, decision=payload.decision, comment=payload.comment
    )
    return TransitionResponse(document_id=document_id, status=updated["status"])


@router.post("/{document_id}/approve", response_model=TransitionResponse)
async def approve_document(
    document_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(_require_approve)],
    _fence: Annotated[dict, Depends(_require_approve_geofence)],
) -> TransitionResponse:
    document = await _get_document_or_404(db, document_id)
    result = await workflow.approve(db, document=document, actor=user)
    anchor = result.get("anchor")
    return TransitionResponse(
        document_id=document_id,
        status=result["document"]["status"],
        version_id=str(result["version"]["_id"]),
        anchor_status=anchor["status"] if anchor else None,
        tx_hash=anchor.get("tx_hash") if anchor else None,
    )


@router.post("/{document_id}/amend", response_model=TransitionResponse)
async def request_amendment(
    document_id: str,
    payload: AmendRequest,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(_require_amend)],
    _fence: Annotated[dict, Depends(_require_amend_geofence)],
) -> TransitionResponse:
    document = await _get_document_or_404(db, document_id)
    updated = await workflow.request_amendment(
        db, document=document, actor=user, reason=payload.reason
    )
    return TransitionResponse(document_id=document_id, status=updated["status"])


@router.post("/{document_id}/archive", response_model=TransitionResponse)
async def archive_document(
    document_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(_require_archive)],
) -> TransitionResponse:
    document = await _get_document_or_404(db, document_id)
    updated = await workflow.archive(db, document=document, actor=user)
    return TransitionResponse(document_id=document_id, status=updated["status"])
