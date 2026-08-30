"""blockchain module service layer.

`blockchain_anchors` is the off-chain record of every anchor attempt.
`anchor_document_version` is the one integration point a later phase (6)
calls after a document is approved — nothing in this module (or anywhere
else) lets a user trigger an anchor directly (Guardrail #3).

Failure handling follows Plan Part 12: an RPC/contract error never raises
out of `anchor_document_version` — it's recorded as a FAILED row so the
caller can keep the document usable and retry later.
"""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.modules.blockchain.models import (
    BLOCKCHAIN_ANCHORS_COLLECTION,
    ETHERSCAN_TX_BASE,
    NETWORK,
    AnchorStatus,
)
from app.services import blockchain as chain


def etherscan_url(tx_hash: str) -> str:
    return f"{ETHERSCAN_TX_BASE}/{tx_hash}"


async def create_pending_anchor(
    db: AsyncIOMotorDatabase,
    *,
    document_id: ObjectId,
    version_id: ObjectId,
    sha256: str,
    event_type: int,
    tx_hash: str,
) -> dict[str, Any]:
    settings = get_settings()
    doc = {
        "document_id": document_id,
        "version_id": version_id,
        "sha256": sha256,
        "event_type": event_type,
        "tx_hash": tx_hash,
        "block_number": None,
        "contract_address": settings.CONTRACT_ADDRESS,
        "network": NETWORK,
        "status": AnchorStatus.PENDING.value,
        "error": None,
        "created_at": datetime.now(UTC),
        "confirmed_at": None,
    }
    result = await db[BLOCKCHAIN_ANCHORS_COLLECTION].insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def _create_failed_anchor(
    db: AsyncIOMotorDatabase,
    *,
    document_id: ObjectId,
    version_id: ObjectId,
    sha256: str,
    event_type: int,
    error: str,
) -> dict[str, Any]:
    settings = get_settings()
    doc = {
        "document_id": document_id,
        "version_id": version_id,
        "sha256": sha256,
        "event_type": event_type,
        # tx_hash is omitted entirely, not set to None: the unique+sparse
        # index on tx_hash only excludes documents where the field is
        # wholly ABSENT — an explicit null is still indexed and would
        # collide the moment a version fails to anchor more than once
        # (e.g. Phase 6's retry-with-backoff on approve).
        "block_number": None,
        "contract_address": settings.CONTRACT_ADDRESS,
        "network": NETWORK,
        "status": AnchorStatus.FAILED.value,
        "error": error,
        "created_at": datetime.now(UTC),
        "confirmed_at": None,
    }
    result = await db[BLOCKCHAIN_ANCHORS_COLLECTION].insert_one(doc)
    doc["_id"] = result.inserted_id
    doc["tx_hash"] = None
    return doc


async def anchor_document_version(
    db: AsyncIOMotorDatabase,
    *,
    document_id: ObjectId,
    version_id: ObjectId,
    version_no: int,
    sha256: str,
    event_type: int,
) -> dict[str, Any]:
    """The integration point Phase 6's approve flow calls. Never raises on
    a chain/RPC failure — records FAILED instead so the app stays usable
    and the document remains APPROVED(pending anchor) for retry."""
    try:
        tx_hash = await chain.anchor_hash(str(document_id), version_no, sha256, event_type)
    except Exception as exc:
        return await _create_failed_anchor(
            db,
            document_id=document_id,
            version_id=version_id,
            sha256=sha256,
            event_type=event_type,
            error=str(exc),
        )

    return await create_pending_anchor(
        db,
        document_id=document_id,
        version_id=version_id,
        sha256=sha256,
        event_type=event_type,
        tx_hash=tx_hash,
    )


async def mark_confirmed(db: AsyncIOMotorDatabase, anchor_id: ObjectId, block_number: int) -> None:
    await db[BLOCKCHAIN_ANCHORS_COLLECTION].update_one(
        {"_id": anchor_id},
        {
            "$set": {
                "status": AnchorStatus.CONFIRMED.value,
                "block_number": block_number,
                "confirmed_at": datetime.now(UTC),
            }
        },
    )


async def mark_failed(db: AsyncIOMotorDatabase, anchor_id: ObjectId, error: str) -> None:
    await db[BLOCKCHAIN_ANCHORS_COLLECTION].update_one(
        {"_id": anchor_id}, {"$set": {"status": AnchorStatus.FAILED.value, "error": error}}
    )


async def get_latest_anchor_for_version(
    db: AsyncIOMotorDatabase, version_id: str
) -> dict[str, Any] | None:
    try:
        oid = ObjectId(version_id)
    except InvalidId:
        return None
    return await db[BLOCKCHAIN_ANCHORS_COLLECTION].find_one(
        {"version_id": oid}, sort=[("created_at", -1)]
    )
