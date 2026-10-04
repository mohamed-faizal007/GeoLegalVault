"""blockchain module router.

No endpoint here (or anywhere) anchors on demand: anchoring is only ever a side effect of
document approval, wired up in Phase 6 (Guardrail #3). The one write is the admin
re-queue (D-041): a *request* that the worker re-drive an anchor the system already owes.
It never contacts the chain, never signs, and names nothing to anchor: the hash comes
from the DB version row, and the worker signs.
"""

from typing import Annotated

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.db import get_db
from app.core.rbac import ANCHOR_RETRY, ANCHOR_VIEW, DOCUMENT_VIEW, has_permission, require
from app.modules.audit import service as audit
from app.modules.blockchain import retry, service
from app.modules.blockchain.schemas import (
    AnchorAttentionItem,
    AnchorAttentionOut,
    AnchorOut,
    AnchorRetryOut,
    AnchorRetryRequest,
    OnchainAnchor,
)
from app.modules.documents import service as documents_service
from app.modules.versions.service import get_version_by_id
from app.services import blockchain as chain
from app.services.anchor_errors import public_error
from app.services.geofence import require_geofence

router = APIRouter(prefix="/blockchain", tags=["blockchain"])

_require_view = require(DOCUMENT_VIEW)
_require_anchor_view = require(ANCHOR_VIEW)
_require_anchor_retry = require(ANCHOR_RETRY)
_require_retry_geofence = require_geofence("anchor_retry")


@router.get("/anchor/{version_id}", response_model=AnchorOut)
async def get_anchor(
    version_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _actor: Annotated[dict, Depends(_require_view)],
) -> AnchorOut:
    anchor = await service.get_latest_anchor_for_version(db, version_id)
    if anchor is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="No anchor recorded for this version"
        )

    onchain: OnchainAnchor | None = None
    if anchor.get("tx_hash"):
        version = await get_version_by_id(db, version_id)
        if version is not None:
            try:
                result = await chain.get_onchain_anchor(
                    str(anchor["document_id"]), version["version_no"]
                )
                onchain = OnchainAnchor(**result)
            except Exception:
                onchain = None

    return AnchorOut(
        id=str(anchor["_id"]),
        document_id=str(anchor["document_id"]),
        version_id=str(anchor["version_id"]),
        sha256=anchor["sha256"],
        event_type=anchor["event_type"],
        tx_hash=anchor.get("tx_hash"),
        block_number=anchor.get("block_number"),
        contract_address=anchor["contract_address"],
        network=anchor["network"],
        status=anchor["status"],
        created_at=anchor["created_at"],
        confirmed_at=anchor.get("confirmed_at"),
        etherscan_url=service.etherscan_url(anchor["tx_hash"]) if anchor.get("tx_hash") else None,
        onchain=onchain,
        error=public_error(anchor.get("error")),
    )


@router.get("/anchors/attention", response_model=AnchorAttentionOut)
async def anchors_needing_attention(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(_require_anchor_view)],
) -> AnchorAttentionOut:
    """Documents left APPROVED because their anchor has not landed. Read-only."""
    items = await retry.attention_items(
        db, caller_can_retry=has_permission(user["role"], ANCHOR_RETRY)
    )
    return AnchorAttentionOut(
        items=[AnchorAttentionItem(**item) for item in items], total=len(items)
    )


@router.post("/anchors/{document_id}/retry", response_model=AnchorRetryOut)
async def requeue_anchor(
    document_id: str,
    payload: AnchorRetryRequest,
    request: Request,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(_require_anchor_retry)],
    _fence: Annotated[dict, Depends(_require_retry_geofence)],
) -> AnchorRetryOut:
    """Admin-only, audited re-queue. JWT -> RBAC -> geofence -> validation -> action ->
    audit (Guardrail #5). The worker, not this request, does any signing."""
    try:
        oid = ObjectId(document_id)
    except InvalidId:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found") from None
    document = await documents_service.get_document_by_id(db, str(oid))
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")

    updated = await retry.requeue(db, document, actor_id=user["_id"])
    await audit.record(
        actor_id=user["_id"],
        action="ANCHOR_RETRY_REQUESTED",
        target_type="document",
        target_id=oid,
        result="SUCCESS",
        ip=request.client.host if request.client else None,
        meta={"reason": payload.reason},
    )
    return AnchorRetryOut(
        document_id=document_id,
        state=retry.RETRYING,
        next_attempt_at=updated[retry.ANCHOR_RETRY]["next_attempt_at"],
    )
