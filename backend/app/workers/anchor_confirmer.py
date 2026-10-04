"""The one optional background worker (Guardrail #10): it confirms PENDING anchors and
re-drives anchors that did not land, so a document is never left stuck in APPROVED
(REL-01, D-037..D-040).

Run it with `python -m app.workers.anchor_confirmer` (loop), `--once` (a single pass),
`--dry-run` (print what it would do; no writes, no transactions) or `--healthcheck`.

Each pass does two things:

1. `confirm_pending_anchors`: promote confirmed txs; mark a reverted tx FAILED; declare a
   tx `TX_DROPPED` only when it is older than ANCHOR_PENDING_TIMEOUT_SEC, has no receipt
   **and the node no longer knows it** (a tx still in the mempool is waiting, not lost).
2. `reconcile_stuck_documents`: for each APPROVED document under a lease taken by
   compare-and-swap, in this order: leave a PENDING anchor alone; finish an interrupted
   promotion for a CONFIRMED one; ask the chain (adopt a matching hash, or fail
   permanently on a different one); check the stored object exists; only then send. The
   hash always comes from the DB version row and only the service wallet signs
   (Guardrails #1, #3).

Errors are stored, logged and heartbeat-ed as the fixed codes from `anchor_errors` only
(D-020); anything logged is passed through `redact_secrets` first.
"""

import argparse
import asyncio
import logging
import uuid
from datetime import timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.modules.audit import service as audit
from app.modules.blockchain import retry
from app.modules.blockchain import service as blockchain_service
from app.modules.blockchain.models import (
    BLOCKCHAIN_ANCHORS_COLLECTION,
    AnchorEventType,
    AnchorStatus,
)
from app.modules.documents import service as documents_service
from app.modules.documents import workflow
from app.modules.documents.models import DOCUMENTS_COLLECTION, DocumentStatus
from app.modules.versions import service as versions_service
from app.modules.versions.models import VersionStatus
from app.services import blockchain as chain
from app.services import storage
from app.services.anchor_errors import (
    ALREADY_ANCHORED,
    ANCHOR_FAILED,
    REVERTED,
    STORED_OBJECT_MISSING,
    TX_DROPPED,
    classify_anchor_error,
    public_error,
    redact_secrets,
)
from app.workers import heartbeat

_logger = logging.getLogger(__name__)

WORKER_ID = "anchor_worker"


def _log_failure(stage: str, exc: BaseException, ref: Any) -> str:
    code = classify_anchor_error(exc)
    _logger.error(
        "anchor worker: %s failed (%s) for %s: %s",
        stage,
        code,
        ref,
        redact_secrets(f"{type(exc).__name__}: {exc}"),
    )
    return code


# --- 1. PENDING anchors ---------------------------------------------------------------


async def _declare_dropped_if_lost(db: AsyncIOMotorDatabase, anchor_doc: dict[str, Any]) -> None:
    settings = get_settings()
    age = retry.now() - retry.aware(anchor_doc["created_at"])
    if age < timedelta(seconds=settings.ANCHOR_PENDING_TIMEOUT_SEC):
        return
    if await chain.tx_known(anchor_doc["tx_hash"]):
        return  # still in the node's mempool (or mined, short of the confirmation depth)
    if not await blockchain_service.fail_pending(db, anchor_doc["_id"], TX_DROPPED):
        return  # another pass got there first

    document_id = anchor_doc["document_id"]
    await documents_service.set_anchor_alert(db, document_id, True)
    document = await documents_service.get_document_by_id(db, str(document_id))
    if document is not None and document["status"] == DocumentStatus.APPROVED.value:
        await retry.ensure_queue(
            db, document_id, queued_at=retry.aware(anchor_doc["created_at"]), last_error=TX_DROPPED
        )
        decision = await retry.record_unleased_failure(db, document_id, TX_DROPPED)
        if decision.permanent:
            await retry.audit_permanent_failure(anchor_doc["version_id"], decision.reason)
    _logger.warning("anchor worker: tx for version %s was dropped", anchor_doc["version_id"])


async def _confirm_one(db: AsyncIOMotorDatabase, anchor_doc: dict[str, Any]) -> int:
    receipt = await chain.confirm_tx(anchor_doc["tx_hash"])
    if receipt is None:
        await _declare_dropped_if_lost(db, anchor_doc)
        return 0

    version = await versions_service.get_version_by_id(db, str(anchor_doc["version_id"]))
    document = await documents_service.get_document_by_id(db, str(anchor_doc["document_id"]))
    if version is None or document is None:
        return 0

    if receipt["status"] != 1:
        if await blockchain_service.fail_pending(db, anchor_doc["_id"], REVERTED):
            await documents_service.set_anchor_alert(db, document["_id"], True)
            if document["status"] == DocumentStatus.APPROVED.value:
                await retry.ensure_queue(
                    db,
                    document["_id"],
                    queued_at=retry.aware(anchor_doc["created_at"]),
                    last_error=REVERTED,
                )
                decision = await retry.record_unleased_failure(db, document["_id"], REVERTED)
                if decision.permanent:
                    await retry.audit_permanent_failure(version["_id"], decision.reason)
        return 0

    await workflow.promote_confirmed_anchor(
        db,
        document=document,
        version=version,
        anchor_doc=anchor_doc,
        block_number=receipt["block_number"],
    )
    return 1


async def confirm_pending_anchors(db: AsyncIOMotorDatabase) -> int:
    """One pass over every PENDING anchor. Returns how many were promoted to ACTIVE.
    One bad anchor (or an RPC error on it) never stops the rest."""
    promoted = 0
    cursor = db[BLOCKCHAIN_ANCHORS_COLLECTION].find({"status": AnchorStatus.PENDING.value})
    async for anchor_doc in cursor:
        try:
            promoted += await _confirm_one(db, anchor_doc)
        except Exception as exc:
            _log_failure("confirm", exc, anchor_doc["_id"])
    return promoted


# --- 2. documents stuck in APPROVED -----------------------------------------------------


async def _fail(
    db: AsyncIOMotorDatabase,
    document: dict[str, Any],
    version: dict[str, Any],
    code: str,
) -> dict[str, Any]:
    """Record one failed attempt; returns the `anchor_retry` fields to write."""
    attempts = (document.get(retry.ANCHOR_RETRY) or {}).get("attempts", 0)
    updates, decision = retry.failure_updates(attempts, code)
    await documents_service.set_anchor_alert(db, document["_id"], True)
    if decision.permanent:
        await retry.audit_permanent_failure(version["_id"], decision.reason)
    return updates


async def _fail_permanently(
    db: AsyncIOMotorDatabase, document: dict[str, Any], version: dict[str, Any], code: str
) -> dict[str, Any]:
    attempts = (document.get(retry.ANCHOR_RETRY) or {}).get("attempts", 0)
    moment = retry.now()
    await documents_service.set_anchor_alert(db, document["_id"], True)
    await retry.audit_permanent_failure(version["_id"], code)
    return {
        "attempts": attempts + 1,
        "last_error": code,
        "last_attempt_at": moment,
        "next_attempt_at": moment,
        "permanent": True,
        "permanent_reason": code,
    }


async def _attempt(
    db: AsyncIOMotorDatabase, document: dict[str, Any], version: dict[str, Any]
) -> dict[str, Any]:
    """One attempt, under the lease (D-037's idempotency order). Returns the
    `anchor_retry` fields to write when the lease is released."""
    document_id = document["_id"]
    sha256 = version["sha256"]

    # 1. An anchor already exists? Judged by status, never by `live` (legacy rows lack it).
    if await retry.anchors_with_status(db, version["_id"], AnchorStatus.PENDING):
        return {}
    confirmed = await retry.anchors_with_status(db, version["_id"], AnchorStatus.CONFIRMED)
    if confirmed:
        await workflow.complete_promotion(
            db, document=document, version=version, anchor_doc=confirmed[0]
        )
        return {}

    # 2. Does the chain already hold it?
    try:
        onchain = await chain.get_onchain_anchor(str(document_id), version["version_no"])
    except Exception as exc:
        return await _fail(db, document, version, _log_failure("chain read", exc, document_id))
    if onchain["exists"]:
        if onchain["hash"].removeprefix("0x").lower() != sha256.lower():
            return await _fail_permanently(db, document, version, ALREADY_ANCHORED)
        anchor_doc = await blockchain_service.create_adopted_anchor(
            db,
            document_id=document_id,
            version_id=version["_id"],
            sha256=sha256,
            event_type=int(onchain["event_type"]),
        )
        await audit.record(
            actor_id="SYSTEM",
            action="ANCHOR_ADOPTED",
            target_type="version",
            target_id=version["_id"],
            result="SUCCESS",
            meta={},
        )
        await workflow.complete_promotion(
            db, document=document, version=version, anchor_doc=anchor_doc
        )
        return {}

    # 3. Is the file there? Only an authoritative "not found" is permanent (D-039).
    try:
        present = await asyncio.to_thread(storage.object_exists, version["storage_key"])
    except Exception as exc:
        _log_failure("storage check", exc, document_id)
        return await _fail(db, document, version, ANCHOR_FAILED)
    if not present:
        return await _fail_permanently(db, document, version, STORED_OBJECT_MISSING)

    # 4. Send. `anchor_document_version` records a PENDING row (the confirm pass takes it
    # from here) or a FAILED one with a fixed error code.
    anchor_doc = await blockchain_service.anchor_document_version(
        db,
        document_id=document_id,
        version_id=version["_id"],
        version_no=version["version_no"],
        sha256=sha256,
        event_type=int(AnchorEventType.APPROVED),
    )
    if anchor_doc["status"] == AnchorStatus.PENDING.value:
        return {"last_attempt_at": retry.now()}
    return await _fail(db, document, version, anchor_doc.get("error") or ANCHOR_FAILED)


async def _reconcile_document(
    db: AsyncIOMotorDatabase, document: dict[str, Any], owner: str
) -> bool:
    version = await versions_service.get_latest_version(db, document["_id"])
    if version is None or version["status"] != VersionStatus.APPROVED.value:
        return False
    if await retry.anchors_with_status(db, version["_id"], AnchorStatus.PENDING):
        return False  # the confirm pass owns it

    state = document.get(retry.ANCHOR_RETRY)
    if state is None:
        queued_at = await retry.effective_queued_at(db, document, version["_id"])
        failed = await db[BLOCKCHAIN_ANCHORS_COLLECTION].find_one(
            {"version_id": version["_id"], "status": AnchorStatus.FAILED.value},
            sort=[("created_at", -1)],
        )
        await retry.ensure_queue(
            db,
            document["_id"],
            queued_at=queued_at,
            last_error=public_error(failed.get("error")) if failed else None,
        )
        document = await documents_service.get_document_by_id(db, str(document["_id"]))
        state = (document or {}).get(retry.ANCHOR_RETRY)
        if state is None:
            return False

    if state.get("permanent") or retry.too_old_for_auto_retry(state.get("queued_at")):
        return False  # permanent, or "needs admin retry": never auto-sent (D-040)
    claimed = await retry.claim_lease(db, document["_id"], owner)
    if claimed is None:
        return False  # not due yet, or another worker holds it

    updates: dict[str, Any] = {}
    try:
        try:
            updates = await _attempt(db, claimed, version)
        except Exception as exc:
            code = _log_failure("attempt", exc, document["_id"])
            updates = await _fail(db, claimed, version, code)
    finally:
        await retry.release_lease(db, document["_id"], owner, updates)
    return True


async def reconcile_stuck_documents(db: AsyncIOMotorDatabase) -> int:
    """One pass over every APPROVED document. Returns how many were attempted."""
    # unique per pass, so one pass can never release a lease another pass holds
    owner = f"{WORKER_ID}:{uuid.uuid4().hex[:8]}"
    attempted = 0
    cursor = db[DOCUMENTS_COLLECTION].find({"status": DocumentStatus.APPROVED.value})
    async for document in cursor:
        try:
            attempted += int(await _reconcile_document(db, document, owner))
        except Exception as exc:
            _log_failure("reconcile", exc, document["_id"])
    return attempted


async def run_pass(db: AsyncIOMotorDatabase) -> dict[str, int]:
    promoted = await confirm_pending_anchors(db)
    attempted = await reconcile_stuck_documents(db)
    return {"promoted": promoted, "attempted": attempted}


async def run_forever(db: AsyncIOMotorDatabase, *, interval_sec: float | None = None) -> None:
    """The loop. An error in a pass is recorded (as a code) in the heartbeat and the loop
    carries on; only cancellation stops it."""
    interval = get_settings().ANCHOR_WORKER_INTERVAL_SEC if interval_sec is None else interval_sec
    while True:
        try:
            await run_pass(db)
            await heartbeat.beat(db)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log_failure("pass", exc, WORKER_ID)
            try:
                await heartbeat.beat(db, error=exc)
            except Exception as beat_exc:
                _log_failure("heartbeat", beat_exc, WORKER_ID)
        await asyncio.sleep(interval)


# --- --dry-run ---------------------------------------------------------------------------


async def plan_dry_run(db: AsyncIOMotorDatabase) -> list[dict[str, Any]]:
    """What a pass would do, per APPROVED document, with no writes and no transactions.
    The read-only probes (`getAnchor` eth_call, storage HEAD) make the plan accurate;
    nothing is built, signed or sent."""
    settings = get_settings()
    moment = retry.now()
    plan: list[dict[str, Any]] = []
    cursor = db[DOCUMENTS_COLLECTION].find({"status": DocumentStatus.APPROVED.value}).sort("_id", 1)
    async for document in cursor:
        version = await versions_service.get_latest_version(db, document["_id"])
        if version is None or version["status"] != VersionStatus.APPROVED.value:
            continue
        state = document.get(retry.ANCHOR_RETRY) or {}
        queued_at = await retry.effective_queued_at(db, document, version["_id"])
        pending = await retry.anchors_with_status(db, version["_id"], AnchorStatus.PENDING)
        confirmed = await retry.anchors_with_status(db, version["_id"], AnchorStatus.CONFIRMED)

        chain_state: str | None = None
        object_present: bool | None = None
        if not pending and not confirmed:
            try:
                onchain = await chain.get_onchain_anchor(
                    str(document["_id"]), version["version_no"]
                )
                if not onchain["exists"]:
                    chain_state = "ABSENT"
                elif onchain["hash"].removeprefix("0x").lower() == version["sha256"].lower():
                    chain_state = "SAME_HASH"
                else:
                    chain_state = "DIFFERENT_HASH"
            except Exception as exc:
                _log_failure("dry-run chain read", exc, document["_id"])
                chain_state = "UNKNOWN"
            try:
                object_present = await asyncio.to_thread(
                    storage.object_exists, version["storage_key"]
                )
            except Exception as exc:
                _log_failure("dry-run storage check", exc, document["_id"])

        if pending:
            action = "AWAITING_CONFIRMATION"
        elif confirmed:
            action = "WOULD_FINISH_PROMOTION"
        elif state.get("permanent"):
            action = "PERMANENT_FAILURE"
        elif retry.too_old_for_auto_retry(queued_at, settings):
            action = "NEEDS_ADMIN_RETRY"
        elif chain_state == "SAME_HASH":
            action = "WOULD_ADOPT"
        elif chain_state == "DIFFERENT_HASH":
            action = "WOULD_MARK_PERMANENT_ALREADY_ANCHORED"
        elif chain_state == "UNKNOWN":
            action = "CHAIN_UNREACHABLE_WOULD_RETRY_LATER"
        elif object_present is False:
            action = "WOULD_MARK_PERMANENT_STORED_OBJECT_MISSING"
        elif object_present is None:
            action = "STORAGE_UNREACHABLE_WOULD_RETRY_LATER"
        else:
            action = "WOULD_SEND"

        last_error = state.get("last_error")
        if last_error is None:  # legacy documents: fall back to the latest failed attempt
            failed = await db[BLOCKCHAIN_ANCHORS_COLLECTION].find_one(
                {"version_id": version["_id"], "status": AnchorStatus.FAILED.value},
                sort=[("created_at", -1)],
            )
            last_error = failed.get("error") if failed else None

        next_attempt = retry.aware(state.get("next_attempt_at"))
        due_in = max(0.0, (next_attempt - moment).total_seconds()) if next_attempt else 0.0
        plan.append(
            {
                "document_id": str(document["_id"]),
                "title": document["title"],
                "version_no": version["version_no"],
                "action": action,
                "would_send": action == "WOULD_SEND",
                "chain_state": chain_state,
                "chain_has_hash": (
                    None if chain_state in (None, "UNKNOWN") else chain_state == "SAME_HASH"
                ),
                "object_exists": object_present,
                "attempts": state.get("attempts", 0),
                "last_error": public_error(last_error),
                "age_days": round((moment - queued_at).total_seconds() / 86400, 1),
                "due_in_sec": round(due_in, 1),
            }
        )
    return plan


def _print_plan(plan: list[dict[str, Any]]) -> None:
    print("anchor worker dry run: no writes, no transactions")
    print(f"auto-retry age cutoff: {get_settings().ANCHOR_AUTO_RETRY_MAX_AGE_DAYS} days")
    print(f"APPROVED documents considered: {len(plan)}")
    for entry in plan:
        chain_label = entry["chain_state"] or "n/a"
        if entry["object_exists"] is None:
            object_label = "n/a" if entry["chain_state"] is None else "UNKNOWN"
        else:
            object_label = "present" if entry["object_exists"] else "MISSING"
        print(
            f"- {entry['document_id']} {entry['title']!r} v{entry['version_no']}\n"
            f"    action={entry['action']} would_send={entry['would_send']} "
            f"chain={chain_label} object={object_label}\n"
            f"    age={entry['age_days']}d attempts={entry['attempts']} "
            f"last_error={entry['last_error']} due_in={entry['due_in_sec']}s"
        )
    sends = sum(1 for entry in plan if entry["would_send"])
    print(f"transactions this pass would send: {sends}")


# --- CLI ----------------------------------------------------------------------------------


async def _amain(args: argparse.Namespace) -> int:
    from app.core.db import close_client, get_database

    db = get_database()
    try:
        if args.healthcheck:
            try:
                return 0 if await heartbeat.is_fresh(db) else 1
            except Exception:
                return 1
        if args.dry_run:
            _print_plan(await plan_dry_run(db))
            return 0
        if args.once:
            try:
                await run_pass(db)
            except Exception as exc:
                _log_failure("pass", exc, WORKER_ID)
                await heartbeat.beat(db, error=exc)
                return 1
            await heartbeat.beat(db)
            return 0
        await run_forever(db)
        return 0
    finally:
        await close_client()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GeoLegalVault anchor worker (Guardrail #10)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="run a single pass and exit")
    mode.add_argument("--dry-run", action="store_true", help="print the plan; no writes, no txs")
    mode.add_argument("--healthcheck", action="store_true", help="exit 0 if the heartbeat is fresh")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    return asyncio.run(_amain(args))


if __name__ == "__main__":  # pragma: no cover - exercised through subprocess tests
    raise SystemExit(main())
