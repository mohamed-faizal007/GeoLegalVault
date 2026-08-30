"""versions module service layer — document_versions is insert-only.

The collection has exactly two write paths: `insert_version` (creating a new
version) and `update_status` (the one whitelisted field a later phase may
change, e.g. DRAFT -> ... -> ACTIVE). Nothing else here mutates a version;
content/hash/storage_key are fixed forever once inserted.
"""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.modules.versions.models import DOCUMENT_VERSIONS_COLLECTION, VersionStatus
from app.modules.versions.schemas import VersionOut


def to_out(doc: dict[str, Any]) -> VersionOut:
    return VersionOut(
        id=str(doc["_id"]),
        document_id=str(doc["document_id"]),
        version_no=doc["version_no"],
        sha256=doc["sha256"],
        prev_version_hash=doc.get("prev_version_hash"),
        storage_key=doc["storage_key"],
        size_bytes=doc["size_bytes"],
        mime=doc["mime"],
        status=doc["status"],
        uploaded_by=str(doc["uploaded_by"]),
        uploaded_at=doc["uploaded_at"],
        anchored=doc.get("anchored", False),
        anchor_id=str(doc["anchor_id"]) if doc.get("anchor_id") else None,
    )


async def insert_version(
    db: AsyncIOMotorDatabase,
    *,
    document_id: ObjectId,
    version_no: int,
    sha256: str,
    prev_version_hash: str | None,
    storage_key: str,
    size_bytes: int,
    mime: str,
    uploaded_by: ObjectId,
) -> dict[str, Any]:
    doc = {
        "document_id": document_id,
        "version_no": version_no,
        "sha256": sha256,
        "prev_version_hash": prev_version_hash,
        "storage_key": storage_key,
        "size_bytes": size_bytes,
        "mime": mime,
        "status": VersionStatus.DRAFT.value,
        "uploaded_by": uploaded_by,
        "uploaded_at": datetime.now(UTC),
        "anchored": False,
        "anchor_id": None,
    }
    result = await db[DOCUMENT_VERSIONS_COLLECTION].insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_version_by_id(db: AsyncIOMotorDatabase, version_id: str) -> dict[str, Any] | None:
    try:
        oid = ObjectId(version_id)
    except InvalidId:
        return None
    return await db[DOCUMENT_VERSIONS_COLLECTION].find_one({"_id": oid})


async def list_versions_for_document(
    db: AsyncIOMotorDatabase, document_id: ObjectId
) -> list[dict[str, Any]]:
    cursor = db[DOCUMENT_VERSIONS_COLLECTION].find({"document_id": document_id}).sort(
        "version_no", 1
    )
    return [doc async for doc in cursor]


async def update_status(
    db: AsyncIOMotorDatabase, version_id: ObjectId, status: VersionStatus
) -> None:
    """The one whitelisted mutation path for an otherwise-immutable version."""
    await db[DOCUMENT_VERSIONS_COLLECTION].update_one(
        {"_id": version_id}, {"$set": {"status": status.value}}
    )


async def mark_confirmed_anchor(
    db: AsyncIOMotorDatabase,
    version_id: ObjectId,
    *,
    anchor_id: ObjectId,
    status: VersionStatus,
) -> None:
    """Whitelisted mutation: records the confirmed on-chain anchor on a
    version. Content/hash/storage_key are still never touched (Guardrail #7)
    — only the anchor bookkeeping and lifecycle status fields change."""
    await db[DOCUMENT_VERSIONS_COLLECTION].update_one(
        {"_id": version_id},
        {"$set": {"anchored": True, "anchor_id": anchor_id, "status": status.value}},
    )


async def get_latest_version(
    db: AsyncIOMotorDatabase, document_id: ObjectId
) -> dict[str, Any] | None:
    """The version currently moving through the lifecycle pipeline — always
    the highest version_no. `documents.current_version_id` is different: it
    only ever points at the version that is presently ACTIVE (live), and is
    updated solely at final activation (see documents/workflow.py)."""
    return await db[DOCUMENT_VERSIONS_COLLECTION].find_one(
        {"document_id": document_id}, sort=[("version_no", -1)]
    )


async def find_active_version_excluding(
    db: AsyncIOMotorDatabase, document_id: ObjectId, *, exclude_version_id: ObjectId
) -> dict[str, Any] | None:
    """The version an amendment supersedes: whichever OTHER version of this
    document is still ACTIVE when a new version is promoted."""
    return await db[DOCUMENT_VERSIONS_COLLECTION].find_one(
        {
            "document_id": document_id,
            "status": VersionStatus.ACTIVE.value,
            "_id": {"$ne": exclude_version_id},
        }
    )
