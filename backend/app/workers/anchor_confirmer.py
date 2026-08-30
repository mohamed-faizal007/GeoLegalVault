"""Background poller for PENDING blockchain_anchors — the optional worker
Plan Part 12 describes (Guardrail #10: "no separate services/queues except
ONE optional background worker for blockchain confirmation polling").

Not required for correctness: `documents.workflow.approve()` already makes
a bounded synchronous confirm attempt before returning. This worker only
mops up anchors that were still PENDING when that window closed — e.g. a
slow Sepolia block — confirming them and promoting their document/version
to ACTIVE via the same `promote_confirmed_anchor` helper `approve()` uses.
"""

import asyncio

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.modules.blockchain import service as blockchain_service
from app.modules.blockchain.models import BLOCKCHAIN_ANCHORS_COLLECTION, AnchorStatus
from app.modules.documents import service as documents_service
from app.modules.documents import workflow
from app.modules.versions import service as versions_service
from app.services import blockchain as chain


async def confirm_pending_anchors(db: AsyncIOMotorDatabase) -> int:
    """One pass over every PENDING anchor. Returns how many were promoted to
    ACTIVE this pass. Safe to call repeatedly — confirm_tx and the promotion
    path are idempotent per (document, version)."""
    promoted = 0
    cursor = db[BLOCKCHAIN_ANCHORS_COLLECTION].find({"status": AnchorStatus.PENDING.value})
    async for anchor_doc in cursor:
        receipt = await chain.confirm_tx(anchor_doc["tx_hash"])
        if receipt is None:
            continue

        version = await versions_service.get_version_by_id(db, str(anchor_doc["version_id"]))
        document = await documents_service.get_document_by_id(db, str(anchor_doc["document_id"]))
        if version is None or document is None:
            continue

        if receipt["status"] != 1:
            await blockchain_service.mark_failed(db, anchor_doc["_id"], "transaction reverted")
            await documents_service.set_anchor_alert(db, document["_id"], True)
            continue

        await workflow.promote_confirmed_anchor(
            db,
            document=document,
            version=version,
            anchor_doc=anchor_doc,
            block_number=receipt["block_number"],
        )
        promoted += 1
    return promoted


async def run_forever(db: AsyncIOMotorDatabase, *, interval_sec: float = 15.0) -> None:
    """Entry point for running this as the one optional background worker,
    e.g. `python -m app.workers.anchor_confirmer`."""
    while True:
        await confirm_pending_anchors(db)
        await asyncio.sleep(interval_sec)


if __name__ == "__main__":  # pragma: no cover — manual/optional invocation
    from app.core.db import get_database

    asyncio.run(run_forever(get_database()))
