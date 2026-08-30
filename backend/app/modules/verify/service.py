"""verify module service layer — the 3-way verification loop (Plan Part 6
Scenario 5, Part 13, Part 17). This is the product's core feature: it is the
only place that independently proves a stored file is still what was
approved, by recomputing SHA-256 from the actual current bytes in object
storage and comparing it against (a) the hash recorded in Mongo at upload
time and (b) the immutable hash read live from the Sepolia contract.

Neither a database compromise (Scenario 5's "attacker edits the stored
hash to match their tampered file") nor a storage compromise alone can
produce a false VERIFIED — only bytes that hash to the value the chain
actually holds can pass all three checks.

A version that was never anchored is NOT_ANCHORED, not an error: the
recomputed/stored comparison is still reported so a draft can be sanity
checked before it ever reaches approval.
"""

import hmac
import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.errors import AppError
from app.modules.audit import service as audit
from app.modules.blockchain import service as blockchain_service
from app.modules.documents import service as documents_service
from app.modules.verify.models import VERIFICATION_RECORDS_COLLECTION, VerificationResult
from app.modules.verify.schemas import VerificationRecordOut, VerifyResponse
from app.modules.versions import service as versions_service
from app.services import blockchain as chain
from app.services import storage
from app.services.hashing import sha256_bytes

_logger = logging.getLogger(__name__)


class VersionNotFound(AppError):
    status_code = 404

    def __init__(self, message: str = "Version not found"):
        super().__init__("NOT_FOUND", message)


class StorageReadFailed(AppError):
    status_code = 503

    def __init__(self, message: str = "could not read the stored file"):
        super().__init__("STORAGE_UNAVAILABLE", message)


def _normalize_hash(value: str) -> str:
    """Both sides of every comparison must be plain lowercase hex: the
    contract read comes back "0x"-prefixed, Mongo/recomputed hashes never
    are."""
    return value.removeprefix("0x").lower()


def to_out(doc: dict[str, Any]) -> VerificationRecordOut:
    return VerificationRecordOut(
        id=str(doc["_id"]),
        version_id=str(doc["version_id"]),
        requested_by=str(doc["requested_by"]),
        recomputed_hash=doc["recomputed_hash"],
        stored_hash=doc["stored_hash"],
        onchain_hash=doc.get("onchain_hash"),
        result=doc["result"],
        created_at=doc["created_at"],
    )


async def _insert_record(
    db: AsyncIOMotorDatabase,
    *,
    version_id: ObjectId,
    requested_by: Any,
    recomputed_hash: str,
    stored_hash: str,
    onchain_hash: str | None,
    result: str,
) -> dict[str, Any]:
    doc = {
        "version_id": version_id,
        "requested_by": requested_by,
        "recomputed_hash": recomputed_hash,
        "stored_hash": stored_hash,
        "onchain_hash": onchain_hash,
        "result": result,
        "created_at": datetime.now(UTC),
    }
    inserted = await db[VERIFICATION_RECORDS_COLLECTION].insert_one(doc)
    doc["_id"] = inserted.inserted_id
    return doc


async def verify_version(
    db: AsyncIOMotorDatabase, *, version_id: str, actor: dict[str, Any]
) -> VerifyResponse:
    version = await versions_service.get_version_by_id(db, version_id)
    if version is None:
        raise VersionNotFound()

    document = await documents_service.get_document_by_id(db, str(version["document_id"]))
    if document is None:
        raise VersionNotFound("owning document not found")

    try:
        data = storage.get_object(version["storage_key"])
    except Exception as exc:
        raise StorageReadFailed() from exc

    recomputed = sha256_bytes(data)
    stored = version["sha256"]

    try:
        onchain = await chain.get_onchain_anchor(
            str(version["document_id"]), version["version_no"]
        )
    except Exception:
        onchain = {"exists": False}

    onchain_hash: str | None = (
        _normalize_hash(onchain["hash"]) if onchain.get("exists") else None
    )

    if onchain_hash is None:
        result = VerificationResult.NOT_ANCHORED
    elif hmac.compare_digest(recomputed, _normalize_hash(stored)) and hmac.compare_digest(
        recomputed, onchain_hash
    ):
        result = VerificationResult.VERIFIED
    else:
        result = VerificationResult.MISMATCH

    anchor = await blockchain_service.get_latest_anchor_for_version(db, version_id)
    tx_hash = anchor.get("tx_hash") if anchor else None
    etherscan_url = blockchain_service.etherscan_url(tx_hash) if tx_hash else None

    await _insert_record(
        db,
        version_id=version["_id"],
        requested_by=actor["_id"],
        recomputed_hash=recomputed,
        stored_hash=stored,
        onchain_hash=onchain_hash,
        result=result.value,
    )

    if result == VerificationResult.MISMATCH:
        await documents_service.set_integrity_flag(db, document["_id"], "TAMPERED")
        _logger.warning(
            "verify: integrity MISMATCH — document flagged TAMPERED",
            extra={
                "document_id": str(document["_id"]),
                "version_id": version_id,
                "recomputed": recomputed,
                "stored": stored,
                "onchain": onchain_hash,
            },
        )
        await audit.record(
            actor_id=actor["_id"],
            action="VERIFY_FAIL",
            target_type="version",
            target_id=version["_id"],
            result="MISMATCH",
        )
    elif result == VerificationResult.VERIFIED:
        await audit.record(
            actor_id=actor["_id"],
            action="VERIFY_PASS",
            target_type="version",
            target_id=version["_id"],
            result="SUCCESS",
        )
    else:
        await audit.record(
            actor_id=actor["_id"],
            action="VERIFY_NOT_ANCHORED",
            target_type="version",
            target_id=version["_id"],
            result="NOT_ANCHORED",
        )

    return VerifyResponse(
        result=result.value,
        recomputed=recomputed,
        stored=stored,
        onchain=onchain_hash,
        tx_hash=tx_hash,
        etherscan_url=etherscan_url,
    )


async def list_verification_history(
    db: AsyncIOMotorDatabase, version_id: str
) -> list[dict[str, Any]]:
    try:
        oid = ObjectId(version_id)
    except InvalidId:
        return []
    cursor = db[VERIFICATION_RECORDS_COLLECTION].find({"version_id": oid}).sort(
        "created_at", -1
    )
    return [doc async for doc in cursor]
