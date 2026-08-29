"""blockchain module router — read-only.

No endpoint here (or anywhere) anchors on demand: anchoring is only ever a
side effect of document approval, wired up in Phase 6 (Guardrail #3).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.db import get_db
from app.core.rbac import DOCUMENT_VIEW, require
from app.modules.blockchain import service
from app.modules.blockchain.schemas import AnchorOut, OnchainAnchor
from app.modules.versions.service import get_version_by_id
from app.services import blockchain as chain

router = APIRouter(prefix="/blockchain", tags=["blockchain"])

_require_view = require(DOCUMENT_VIEW)


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
        error=anchor.get("error"),
    )
