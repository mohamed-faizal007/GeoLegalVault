"""Retry state and policy for anchors that did not land (REL-01, D-037..D-041).

State lives on the document as `anchor_retry` (a stuck document is by definition one
in APPROVED); `blockchain_anchors` stays an append-only log with one row per tx sent
or adopted, and `document_versions` is never touched (Guardrail #7).

Nothing here signs or sends. The worker (`app/workers/anchor_confirmer.py`) is the
only caller that does, through `blockchain_service.anchor_document_version`; the API
can only *re-queue* (`requeue`), never act on the chain (Guardrail #3).
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.core.clearance import HIDDEN_TITLE, can_see
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.modules.audit import service as audit
from app.modules.blockchain.models import BLOCKCHAIN_ANCHORS_COLLECTION, AnchorStatus
from app.modules.documents.models import DOCUMENTS_COLLECTION, DocumentStatus
from app.services import anchor_errors as codes

_logger = logging.getLogger(__name__)

ANCHOR_RETRY = "anchor_retry"

# Attention states (D-041).
RETRYING = "RETRYING"
AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
PERMANENT_FAILURE = "PERMANENT_FAILURE"
NEEDS_ADMIN_RETRY = "NEEDS_ADMIN_RETRY"

# Failures that retrying cannot fix: a missing writer role, missing config, a file that
# is not in storage.
_PERMANENT_NOW = frozenset(
    {codes.NOT_AUTHORIZED, codes.NOT_CONFIGURED, codes.STORED_OBJECT_MISSING}
)


class AnchorNotRetryable(AppError):
    status_code = 409

    def __init__(self, message: str):
        super().__init__("ANCHOR_NOT_RETRYABLE", message)


@dataclass(frozen=True)
class RetryDecision:
    permanent: bool
    reason: str | None
    delay_sec: float


def _backoff(failures: int, base: float, cap: float) -> float:
    return min(cap, base * 2 ** (failures - 1))


def _transient_delay(failures: int, s: Settings) -> float:
    return _backoff(failures, s.ANCHOR_RETRY_BASE_SEC, s.ANCHOR_RETRY_CAP_SEC)


def next_after_failure(
    code: str, failures: int, settings: Settings | None = None
) -> RetryDecision:
    """What to do after the `failures`-th failure (1-based, this one included) with `code`.
    The table is D-038; every number is a setting."""
    s = settings or get_settings()
    if code in _PERMANENT_NOW:
        return RetryDecision(True, code, 0.0)
    if code == codes.REVERTED:
        if failures >= s.ANCHOR_REVERT_MAX_ATTEMPTS:
            return RetryDecision(True, codes.REVERTED, 0.0)
        return RetryDecision(False, None, _transient_delay(failures, s))
    if code == codes.ALREADY_ANCHORED:
        # Whether that is "ours" (adopt) or "someone else's" (permanent) is decided by
        # reading the chain on the next attempt, not by counting. Bounded all the same.
        if failures >= s.ANCHOR_RETRY_MAX_ATTEMPTS:
            return RetryDecision(True, codes.RETRIES_EXHAUSTED, 0.0)
        return RetryDecision(False, None, 0.0)
    if failures >= s.ANCHOR_RETRY_MAX_ATTEMPTS:
        return RetryDecision(True, codes.RETRIES_EXHAUSTED, 0.0)
    if code == codes.INSUFFICIENT_FUNDS:
        delay = _backoff(failures, s.ANCHOR_FUNDS_RETRY_BASE_SEC, s.ANCHOR_FUNDS_RETRY_CAP_SEC)
        return RetryDecision(False, None, delay)
    return RetryDecision(False, None, _transient_delay(failures, s))


# --- time -------------------------------------------------------------------------


def now() -> datetime:
    return datetime.now(UTC)


def aware(value: datetime | None) -> datetime | None:
    """Mongo hands datetimes back naive (UTC)."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def too_old_for_auto_retry(queued_at: datetime | None, settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    queued = aware(queued_at)
    return queued is not None and now() - queued > timedelta(days=s.ANCHOR_AUTO_RETRY_MAX_AGE_DAYS)


# --- anchor rows (by status, never by `live`: legacy rows lack it, D-023/D-037) ---------


async def anchors_with_status(
    db: AsyncIOMotorDatabase, version_id: ObjectId, *statuses: AnchorStatus
) -> list[dict[str, Any]]:
    cursor = db[BLOCKCHAIN_ANCHORS_COLLECTION].find(
        {"version_id": version_id, "status": {"$in": [s.value for s in statuses]}}
    )
    return await cursor.to_list(None)


async def earliest_anchor_time(db: AsyncIOMotorDatabase, version_id: ObjectId) -> datetime | None:
    row = await db[BLOCKCHAIN_ANCHORS_COLLECTION].find_one(
        {"version_id": version_id}, sort=[("created_at", 1)]
    )
    return aware(row["created_at"]) if row else None


async def effective_queued_at(
    db: AsyncIOMotorDatabase, document: dict[str, Any], version_id: ObjectId
) -> datetime:
    """When this document became stuck: the recorded enqueue time; else (legacy rows with
    no `anchor_retry`) the first anchor attempt for the version; else its last update."""
    recorded = (document.get(ANCHOR_RETRY) or {}).get("queued_at")
    if recorded is not None:
        return aware(recorded)
    return await earliest_anchor_time(db, version_id) or aware(document["updated_at"])


# --- queue state --------------------------------------------------------------------


async def enqueue(
    db: AsyncIOMotorDatabase,
    document_id: ObjectId,
    *,
    error_code: str | None,
    queued_at: datetime | None = None,
) -> RetryDecision:
    """Called when `approve()`'s in-request attempts have failed: hand the document to the
    worker. The in-request attempts are not counted in `attempts` (D-038)."""
    s = get_settings()
    moment = now()
    code = error_code or codes.ANCHOR_FAILED
    decision = next_after_failure(code, 1, s)
    state = {
        "attempts": 0,
        "permanent": decision.permanent,
        "permanent_reason": decision.reason,
        "last_error": code,
        "queued_at": queued_at or moment,
        "next_attempt_at": moment + timedelta(seconds=decision.delay_sec),
        "last_attempt_at": None,
        "lease_owner": None,
        "lease_until": None,
    }
    await db[DOCUMENTS_COLLECTION].update_one(
        {"_id": document_id, "status": DocumentStatus.APPROVED.value},
        {"$set": {ANCHOR_RETRY: state}},
    )
    return decision


async def ensure_queue(
    db: AsyncIOMotorDatabase,
    document_id: ObjectId,
    *,
    queued_at: datetime,
    last_error: str | None,
) -> None:
    """For an APPROVED document that has no `anchor_retry` (written before REL-01, or a
    crash before `enqueue`). Idempotent: only the first writer's state sticks."""
    await db[DOCUMENTS_COLLECTION].update_one(
        {
            "_id": document_id,
            "status": DocumentStatus.APPROVED.value,
            ANCHOR_RETRY: {"$exists": False},
        },
        {
            "$set": {
                ANCHOR_RETRY: {
                    "attempts": 0,
                    "permanent": False,
                    "permanent_reason": None,
                    "last_error": last_error,
                    "queued_at": queued_at,
                    "next_attempt_at": now(),
                    "last_attempt_at": None,
                    "lease_owner": None,
                    "lease_until": None,
                }
            }
        },
    )


async def claim_lease(
    db: AsyncIOMotorDatabase, document_id: ObjectId, owner: str
) -> dict[str, Any] | None:
    """Compare-and-swap lease (D-038): exactly one worker gets a document that is due, not
    permanent and not held. The lease (ANCHOR_LEASE_SEC) outlives the confirmation timeout."""
    s = get_settings()
    moment = now()
    return await db[DOCUMENTS_COLLECTION].find_one_and_update(
        {
            "_id": document_id,
            "status": DocumentStatus.APPROVED.value,
            f"{ANCHOR_RETRY}.permanent": {"$ne": True},
            f"{ANCHOR_RETRY}.next_attempt_at": {"$lte": moment},
            "$or": [
                {f"{ANCHOR_RETRY}.lease_until": None},
                {f"{ANCHOR_RETRY}.lease_until": {"$lte": moment}},
            ],
        },
        {
            "$set": {
                f"{ANCHOR_RETRY}.lease_owner": owner,
                f"{ANCHOR_RETRY}.lease_until": moment + timedelta(seconds=s.ANCHOR_LEASE_SEC),
            }
        },
        return_document=ReturnDocument.AFTER,
    )


async def release_lease(
    db: AsyncIOMotorDatabase,
    document_id: ObjectId,
    owner: str,
    updates: dict[str, Any] | None = None,
) -> None:
    """Ends an attempt. A no-op if the lease already expired and someone else holds it."""
    fields = {f"{ANCHOR_RETRY}.{key}": value for key, value in (updates or {}).items()}
    fields[f"{ANCHOR_RETRY}.lease_owner"] = None
    fields[f"{ANCHOR_RETRY}.lease_until"] = None
    await db[DOCUMENTS_COLLECTION].update_one(
        {"_id": document_id, f"{ANCHOR_RETRY}.lease_owner": owner}, {"$set": fields}
    )


def failure_updates(attempts_before: int, code: str) -> tuple[dict[str, Any], RetryDecision]:
    """The `anchor_retry` fields to write after one more failure with `code`."""
    decision = next_after_failure(code, attempts_before + 1, get_settings())
    moment = now()
    return (
        {
            "attempts": attempts_before + 1,
            "last_error": code,
            "last_attempt_at": moment,
            "next_attempt_at": moment + timedelta(seconds=decision.delay_sec),
            "permanent": decision.permanent,
            "permanent_reason": decision.reason,
        },
        decision,
    )


async def record_unleased_failure(
    db: AsyncIOMotorDatabase, document_id: ObjectId, code: str
) -> RetryDecision:
    """A failure found outside an attempt (a dropped or reverted tx seen by the confirm
    pass). Counts as one attempt."""
    document = await db[DOCUMENTS_COLLECTION].find_one({"_id": document_id}, {ANCHOR_RETRY: 1})
    attempts = ((document or {}).get(ANCHOR_RETRY) or {}).get("attempts", 0)
    updates, decision = failure_updates(attempts, code)
    await db[DOCUMENTS_COLLECTION].update_one(
        {"_id": document_id, "status": DocumentStatus.APPROVED.value},
        {"$set": {f"{ANCHOR_RETRY}.{key}": value for key, value in updates.items()}},
    )
    return decision


async def clear(db: AsyncIOMotorDatabase, document_id: ObjectId) -> None:
    """The anchor landed: drop the retry state. History stays in the anchor rows and audit."""
    await db[DOCUMENTS_COLLECTION].update_one({"_id": document_id}, {"$unset": {ANCHOR_RETRY: ""}})


async def audit_permanent_failure(version_id: ObjectId, code: str) -> None:
    _logger.warning("anchor: permanent failure (%s) for version %s", code, version_id)
    await audit.record(
        actor_id="SYSTEM",
        action="ANCHOR_PERMANENT_FAIL",
        target_type="version",
        target_id=version_id,
        result="FAILED",
        meta={"error": code},
    )


async def requeue(
    db: AsyncIOMotorDatabase, document: dict[str, Any], *, actor_id: Any
) -> dict[str, Any]:
    """Admin re-queue (D-041): puts the document back in the worker's queue, as a fresh
    request (attempts and age reset). It never contacts the chain; the worker signs."""
    from app.modules.versions import service as versions_service  # avoids an import cycle

    if document["status"] != DocumentStatus.APPROVED.value:
        raise AnchorNotRetryable(
            f"document is {document['status']}; only an APPROVED document with an unfinished "
            "anchor can be re-queued"
        )
    version = await versions_service.get_latest_version(db, document["_id"])
    if version is None:
        raise AnchorNotRetryable("document has no version")
    in_flight = await anchors_with_status(
        db, version["_id"], AnchorStatus.PENDING, AnchorStatus.CONFIRMED
    )
    if in_flight:
        raise AnchorNotRetryable("an anchor for this version is already in flight or confirmed")

    moment = now()
    claimed = await db[DOCUMENTS_COLLECTION].find_one_and_update(
        {
            "_id": document["_id"],
            "status": DocumentStatus.APPROVED.value,
            "$or": [
                {f"{ANCHOR_RETRY}.lease_until": None},
                {f"{ANCHOR_RETRY}.lease_until": {"$lte": moment}},
            ],
        },
        {
            "$set": {
                f"{ANCHOR_RETRY}.attempts": 0,
                f"{ANCHOR_RETRY}.permanent": False,
                f"{ANCHOR_RETRY}.permanent_reason": None,
                f"{ANCHOR_RETRY}.next_attempt_at": moment,
                f"{ANCHOR_RETRY}.queued_at": moment,
                f"{ANCHOR_RETRY}.requeued_by": actor_id,
                f"{ANCHOR_RETRY}.requeued_at": moment,
                f"{ANCHOR_RETRY}.lease_owner": None,
                f"{ANCHOR_RETRY}.lease_until": None,
                "updated_at": moment,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if claimed is None:
        raise AnchorNotRetryable(
            "the document is being worked on by the anchor worker; try again shortly"
        )
    return claimed


# --- the attention view -------------------------------------------------------------


async def attention_items(
    db: AsyncIOMotorDatabase, *, caller_can_retry: bool, viewer: dict[str, Any]
) -> list[dict[str, Any]]:
    """APPROVED documents whose anchor needs a human's eye (D-041). Read-only.

    An operational alert for everyone with anchor:view; the title of a document above the
    viewer's clearance is withheld (D-051), so an operator can still see and re-queue it."""
    from app.modules.versions import service as versions_service  # avoids an import cycle

    s = get_settings()
    moment = now()
    grace = timedelta(seconds=s.ANCHOR_ATTENTION_GRACE_SEC)
    items: list[dict[str, Any]] = []

    cursor = db[DOCUMENTS_COLLECTION].find({"status": DocumentStatus.APPROVED.value}).limit(500)
    async for document in cursor:
        version = await versions_service.get_latest_version(db, document["_id"])
        if version is None:
            continue
        state = document.get(ANCHOR_RETRY) or {}
        stuck_since = await effective_queued_at(db, document, version["_id"])
        flagged = bool(document.get("anchor_pending_alert")) or bool(state)
        if not flagged and moment - stuck_since <= grace:
            continue  # simply mid-approval

        pending = await anchors_with_status(db, version["_id"], AnchorStatus.PENDING)
        if state.get("permanent"):
            label = PERMANENT_FAILURE
        elif too_old_for_auto_retry(stuck_since, s):
            label = NEEDS_ADMIN_RETRY
        elif pending:
            label = AWAITING_CONFIRMATION
        else:
            label = RETRYING

        permanent = bool(state.get("permanent"))
        last_error = state.get("permanent_reason") if permanent else state.get("last_error")
        if last_error is None:
            failed = await db[BLOCKCHAIN_ANCHORS_COLLECTION].find_one(
                {"version_id": version["_id"], "status": AnchorStatus.FAILED.value},
                sort=[("created_at", -1)],
            )
            last_error = failed.get("error") if failed else None

        items.append(
            {
                "document_id": str(document["_id"]),
                "title": document["title"]
                if can_see(viewer, document.get("classification"))
                else HIDDEN_TITLE,
                "version_no": version["version_no"],
                "state": label,
                "last_error": codes.public_error(last_error),
                "attempts": state.get("attempts", 0),
                "next_attempt_at": None if permanent else state.get("next_attempt_at"),
                "stuck_since": stuck_since,
                "can_retry": caller_can_retry,
            }
        )
    items.sort(key=lambda item: item["stuck_since"])
    return items
