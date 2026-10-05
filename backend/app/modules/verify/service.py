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

"Could not check" is never a verdict (REL-04, D-049). If the chain cannot be read the
result is CHAIN_UNREACHABLE; if the chain answers "no anchor" for a version the database
itself says was anchored it is ANCHOR_MISSING (flagged and audited); a stored object that
is gone is FILE_MISSING. NOT_ANCHORED is reserved for a version the database does not claim
was ever anchored.
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
from app.modules.versions.models import VersionStatus
from app.services import blockchain as chain
from app.services import storage
from app.services.anchor_errors import (
    CONTRACT_NOT_DEPLOYED,
    classify_chain_read_error,
    redact_secrets,
)
from app.services.hashing import sha256_bytes

_logger = logging.getLogger(__name__)

# A version in one of these statuses only gets there through a confirmed anchor.
_POST_ANCHOR_STATUSES = {
    VersionStatus.BLOCKCHAIN_ANCHORED.value,
    VersionStatus.ACTIVE.value,
    VersionStatus.SUPERSEDED.value,
}


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
        reason=doc.get("reason"),
    )


async def _insert_record(
    db: AsyncIOMotorDatabase,
    *,
    version_id: ObjectId,
    requested_by: Any,
    recomputed_hash: str | None,
    stored_hash: str,
    onchain_hash: str | None,
    result: str,
    reason: str | None = None,
) -> dict[str, Any]:
    doc = {
        "version_id": version_id,
        "requested_by": requested_by,
        "recomputed_hash": recomputed_hash,
        "stored_hash": stored_hash,
        "onchain_hash": onchain_hash,
        "result": result,
        "reason": reason,
        "created_at": datetime.now(UTC),
    }
    inserted = await db[VERIFICATION_RECORDS_COLLECTION].insert_one(doc)
    doc["_id"] = inserted.inserted_id
    return doc


async def _database_claims_anchored(db: AsyncIOMotorDatabase, version: dict[str, Any]) -> bool:
    """What the database itself says about this version, independent of the chain. Any one
    signal is enough, so editing a single field (the `anchored` flag, the status, ...) cannot
    quietly turn a missing anchor into a grey "not anchored" (D-049)."""
    return (
        bool(version.get("anchored"))
        or version.get("status") in _POST_ANCHOR_STATUSES
        or await blockchain_service.has_confirmed_anchor(db, version["_id"])
    )


async def verify_version(
    db: AsyncIOMotorDatabase, *, version_id: str, actor: dict[str, Any]
) -> VerifyResponse:
    version = await versions_service.get_version_by_id(db, version_id)
    if version is None:
        raise VersionNotFound()

    document = await documents_service.get_document_by_id(db, str(version["document_id"]))
    if document is None:
        raise VersionNotFound("owning document not found")

    stored = version["sha256"]
    claims_anchored = await _database_claims_anchored(db, version)
    anchor = await blockchain_service.get_latest_anchor_for_version(db, version_id)
    tx_hash = anchor.get("tx_hash") if anchor else None
    etherscan_url = blockchain_service.etherscan_url(tx_hash) if tx_hash else None

    try:
        data = storage.get_object(version["storage_key"])
    except Exception as exc:
        if storage.is_not_found(exc):
            return await _file_missing(
                db,
                version=version,
                document=document,
                actor=actor,
                tx_hash=tx_hash,
                etherscan_url=etherscan_url,
            )
        # Cannot tell whether the file is there: no verdict, but the attempt is on record.
        await audit.record(
            actor_id=actor["_id"],
            action="VERIFY_STORAGE_UNAVAILABLE",
            target_type="version",
            target_id=version["_id"],
            result="STORAGE_UNAVAILABLE",
        )
        raise StorageReadFailed() from exc

    recomputed = sha256_bytes(data)
    local_ok = hmac.compare_digest(recomputed, _normalize_hash(stored))

    onchain_hash: str | None = None
    chain_unreachable = False
    reason: str | None = None
    try:
        onchain = await chain.get_onchain_anchor(
            str(version["document_id"]), version["version_no"]
        )
        if onchain.get("exists"):
            onchain_hash = _normalize_hash(onchain["hash"])
    except Exception as exc:
        # An error is "could not read the chain", never "no anchor" (D-049). Only the
        # definitive "no contract code at the address" counts as the chain saying no.
        reason = classify_chain_read_error(exc)
        chain_unreachable = reason != CONTRACT_NOT_DEPLOYED
        _logger.error(
            "verify: chain read failed (%s) for version %s: %s",
            reason,
            version_id,
            redact_secrets(f"{type(exc).__name__}: {exc}"),
        )

    if onchain_hash is not None:
        result = (
            VerificationResult.VERIFIED
            if local_ok and hmac.compare_digest(recomputed, onchain_hash)
            else VerificationResult.MISMATCH
        )
    elif chain_unreachable:
        # A swapped file is provable without the chain; anything else is simply not checked.
        result = (
            VerificationResult.MISMATCH
            if claims_anchored and not local_ok
            else VerificationResult.CHAIN_UNREACHABLE
        )
    elif not claims_anchored:
        result = VerificationResult.NOT_ANCHORED
    else:
        result = (
            VerificationResult.ANCHOR_MISSING if local_ok else VerificationResult.MISMATCH
        )

    await _insert_record(
        db,
        version_id=version["_id"],
        requested_by=actor["_id"],
        recomputed_hash=recomputed,
        stored_hash=stored,
        onchain_hash=onchain_hash,
        result=result.value,
        reason=reason,
    )
    await _flag_and_audit(
        db,
        result=result,
        version=version,
        document=document,
        actor=actor,
        reason=reason,
        log_detail={"recomputed": recomputed, "stored": stored, "onchain": onchain_hash},
    )

    return VerifyResponse(
        result=result.value,
        recomputed=recomputed,
        stored=stored,
        onchain=onchain_hash,
        tx_hash=tx_hash,
        etherscan_url=etherscan_url,
        reason=reason,
    )


async def _file_missing(
    db: AsyncIOMotorDatabase,
    *,
    version: dict[str, Any],
    document: dict[str, Any],
    actor: dict[str, Any],
    tx_hash: str | None,
    etherscan_url: str | None,
) -> VerifyResponse:
    """The store answered "no such object" for a version row that points at it (D-049)."""
    result = VerificationResult.FILE_MISSING
    await _insert_record(
        db,
        version_id=version["_id"],
        requested_by=actor["_id"],
        recomputed_hash=None,
        stored_hash=version["sha256"],
        onchain_hash=None,
        result=result.value,
    )
    await _flag_and_audit(
        db, result=result, version=version, document=document, actor=actor, reason=None
    )
    return VerifyResponse(
        result=result.value,
        recomputed=None,
        stored=version["sha256"],
        onchain=None,
        tx_hash=tx_hash,
        etherscan_url=etherscan_url,
    )


async def _flag_and_audit(
    db: AsyncIOMotorDatabase,
    *,
    result: VerificationResult,
    version: dict[str, Any],
    document: dict[str, Any],
    actor: dict[str, Any],
    reason: str | None,
    log_detail: dict[str, Any] | None = None,
) -> None:
    """The side effects of a verdict: the integrity flag (if any) and the audit row."""
    meta = {"reason": reason} if reason else None
    if result == VerificationResult.MISMATCH:
        await documents_service.set_integrity_flag(db, document["_id"], "TAMPERED")
        _logger.warning(
            "verify: integrity MISMATCH — document flagged TAMPERED",
            extra={
                "document_id": str(document["_id"]),
                "version_id": str(version["_id"]),
                **(log_detail or {}),
            },
        )
        action, audit_result = "VERIFY_FAIL", "MISMATCH"
    elif result == VerificationResult.VERIFIED:
        action, audit_result = "VERIFY_PASS", "SUCCESS"
    elif result in (VerificationResult.ANCHOR_MISSING, VerificationResult.FILE_MISSING):
        await documents_service.flag_integrity_unconfirmed(db, document["_id"])
        _logger.warning(
            "verify: %s — document flagged UNCONFIRMED",
            result.value,
            extra={"document_id": str(document["_id"]), "version_id": str(version["_id"])},
        )
        action, audit_result = f"VERIFY_{result.value}", result.value
    elif result == VerificationResult.CHAIN_UNREACHABLE:
        action, audit_result = "VERIFY_CHAIN_UNREACHABLE", result.value
    else:
        action, audit_result = "VERIFY_NOT_ANCHORED", "NOT_ANCHORED"
    await audit.record(
        actor_id=actor["_id"],
        action=action,
        target_type="version",
        target_id=version["_id"],
        result=audit_result,
        meta=meta,
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
