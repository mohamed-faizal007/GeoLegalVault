"""versions module router — full version lineage for a document.

Registered under the /documents URL namespace (Part 15's API table has no
standalone /versions path), but kept in its own module/router since the
document_versions collection's insert-only rules are a distinct concern
from the documents collection itself.
"""

from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.db import get_db
from app.core.rbac import DOCUMENT_VIEW, require
from app.modules.documents import access
from app.modules.versions import service
from app.modules.versions.schemas import VersionListOut

router = APIRouter(tags=["versions"])

_require_document_view = require(DOCUMENT_VIEW)


@router.get("/documents/{document_id}/versions", response_model=VersionListOut)
async def list_document_versions(
    document_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    actor: Annotated[dict, Depends(_require_document_view)],
) -> VersionListOut:
    await access.load_visible_document(db, actor, document_id, endpoint="versions")

    versions = await service.list_versions_for_document(db, ObjectId(document_id))
    return VersionListOut(items=[service.to_out(v) for v in versions])
