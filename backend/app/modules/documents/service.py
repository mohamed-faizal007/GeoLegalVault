"""documents module service layer.

Upload flow (Guardrails #4/#5/#7): validate -> put_object(encrypted bucket,
server-generated key) -> sha256 -> insert `documents` + `document_versions`
V1. If storage fails, nothing is written to Mongo at all. If the version
insert somehow fails after the document insert succeeded, the document row
is rolled back — no orphan `documents` metadata either way.
"""

from datetime import UTC, datetime
from typing import Any

import magic
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.documents.models import DOCUMENTS_COLLECTION, DocumentStatus
from app.modules.documents.schemas import DocumentOut
from app.modules.versions import service as versions_service
from app.services import storage
from app.services.hashing import sha256_bytes

# Claimed Content-Type -> the set of magic-byte-detected mime types that are
# an acceptable match for it. OOXML (docx) is a zip container, and libmagic
# database versions vary in whether they identify the specific Office
# subtype or just "application/zip" — both are accepted as truthful.
ALLOWED_MIME_TYPES: dict[str, set[str]] = {
    "application/pdf": {"application/pdf"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    },
    "text/plain": {"text/plain"},
    "image/png": {"image/png"},
    "image/jpeg": {"image/jpeg"},
}


class FileTooLarge(AppError):
    status_code = 413

    def __init__(self, message: str):
        super().__init__("FILE_TOO_LARGE", message)


class UnsupportedMediaType(AppError):
    status_code = 422

    def __init__(self, message: str):
        super().__init__("UNSUPPORTED_MEDIA_TYPE", message)


class MimeMismatch(AppError):
    status_code = 422

    def __init__(self, message: str):
        super().__init__("MIME_MISMATCH", message)


class StorageUnavailable(AppError):
    status_code = 503

    def __init__(self, message: str):
        super().__init__("STORAGE_UNAVAILABLE", message)


class DocumentNotFound(Exception):
    pass


def validate_upload(data: bytes, claimed_content_type: str) -> None:
    settings = get_settings()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise FileTooLarge(f"file exceeds the {settings.MAX_UPLOAD_MB}MB limit")

    accepted_detections = ALLOWED_MIME_TYPES.get(claimed_content_type)
    if accepted_detections is None:
        raise UnsupportedMediaType(f"unsupported content type: {claimed_content_type}")

    detected = magic.from_buffer(data, mime=True)
    if detected not in accepted_detections:
        raise MimeMismatch(
            f"claimed content type {claimed_content_type!r} does not match "
            f"the file's actual content (detected {detected!r})"
        )


def to_out(doc: dict[str, Any]) -> DocumentOut:
    return DocumentOut(
        id=str(doc["_id"]),
        title=doc["title"],
        doc_type=doc["doc_type"],
        classification=doc["classification"],
        owner_id=str(doc["owner_id"]),
        status=doc["status"],
        current_version_id=(
            str(doc["current_version_id"]) if doc.get("current_version_id") else None
        ),
        tags=doc.get("tags", []),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        retention_until=doc.get("retention_until"),
    )


async def create_document_with_v1(
    db: AsyncIOMotorDatabase,
    *,
    title: str,
    doc_type: str,
    classification: str,
    tags: list[str],
    owner_id: ObjectId,
    data: bytes,
    content_type: str,
) -> dict[str, Any]:
    validate_upload(data, content_type)

    document_id = ObjectId()
    storage_key = storage.build_version_key(str(document_id), 1)

    try:
        storage.put_object(data, storage_key, content_type)
    except Exception as exc:
        raise StorageUnavailable("could not store the uploaded file") from exc

    sha256 = sha256_bytes(data)
    now = datetime.now(UTC)

    document_doc = {
        "_id": document_id,
        "title": title,
        "doc_type": doc_type,
        "classification": classification,
        "owner_id": owner_id,
        "status": DocumentStatus.DRAFT.value,
        "current_version_id": None,
        "tags": tags,
        "created_at": now,
        "updated_at": now,
        "retention_until": None,
    }
    await db[DOCUMENTS_COLLECTION].insert_one(document_doc)

    try:
        version_doc = await versions_service.insert_version(
            db,
            document_id=document_id,
            version_no=1,
            sha256=sha256,
            prev_version_hash=None,
            storage_key=storage_key,
            size_bytes=len(data),
            mime=content_type,
            uploaded_by=owner_id,
        )
    except Exception:
        await db[DOCUMENTS_COLLECTION].delete_one({"_id": document_id})
        raise

    document_doc["current_version_id"] = version_doc["_id"]
    await db[DOCUMENTS_COLLECTION].update_one(
        {"_id": document_id}, {"$set": {"current_version_id": version_doc["_id"]}}
    )

    return {"document": document_doc, "version": version_doc}


async def get_document_by_id(db: AsyncIOMotorDatabase, document_id: str) -> dict[str, Any] | None:
    try:
        oid = ObjectId(document_id)
    except InvalidId:
        return None
    return await db[DOCUMENTS_COLLECTION].find_one({"_id": oid})


async def list_documents(
    db: AsyncIOMotorDatabase,
    *,
    query: str | None,
    status: str | None,
    doc_type: str | None,
    owner_id: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    page: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    filters: dict[str, Any] = {}
    if query:
        filters["$text"] = {"$search": query}
    if status:
        filters["status"] = status
    if doc_type:
        filters["doc_type"] = doc_type
    if owner_id:
        try:
            filters["owner_id"] = ObjectId(owner_id)
        except InvalidId:
            filters["owner_id"] = ObjectId()  # a fresh id: guaranteed no match

    date_filter: dict[str, datetime] = {}
    if date_from:
        date_filter["$gte"] = date_from
    if date_to:
        date_filter["$lte"] = date_to
    if date_filter:
        filters["created_at"] = date_filter

    skip = (page - 1) * limit
    cursor = db[DOCUMENTS_COLLECTION].find(filters).sort("created_at", -1).skip(skip).limit(limit)
    items = [doc async for doc in cursor]
    total = await db[DOCUMENTS_COLLECTION].count_documents(filters)
    return items, total
