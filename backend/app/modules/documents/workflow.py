"""documents module — lifecycle state machine (Plan Part 5).

Every transition below validates the document's exact current status
against the Part 5 table (anything else is an illegal transition), applies
the maker != checker rule where the table calls for it, makes the DB change,
and records the intended audit action via the Phase 8 stub
(`app.modules.audit.service.record`) — Phase 8 replaces that function's body
without any call site here changing.

Approval is the only transition that touches the chain, and it does so
automatically as a system consequence of reaching APPROVED — there is no
user-triggered anchoring endpoint anywhere (Guardrail #3). Anchor failure
never raises out of `approve()`: the document stays APPROVED (pending
anchor) and the app stays usable, per Plan Part 12's failure-handling table.

"The current version being processed" is always the version with the
highest version_no (`versions_service.get_latest_version`) — this is what
moves through DRAFT -> ... -> ACTIVE. `documents.current_version_id` is a
different pointer: it only ever names whichever version is presently ACTIVE
(live/downloadable), and is repointed just once, at final activation, so an
amendment's in-review V(n+1) never displaces the still-live V(n) mid-review.
"""

import asyncio
import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.rbac import enforce_maker_checker
from app.modules.audit import service as audit
from app.modules.blockchain import retry as anchor_retry
from app.modules.blockchain import service as blockchain_service
from app.modules.blockchain.models import AnchorEventType, AnchorStatus
from app.modules.documents import service as documents_service
from app.modules.documents.models import DocumentStatus
from app.modules.versions import service as versions_service
from app.modules.versions.models import VersionStatus
from app.services import blockchain as chain
from app.services.anchor_errors import REVERTED

_logger = logging.getLogger(__name__)


class IllegalTransition(AppError):
    status_code = 409

    def __init__(self, message: str):
        super().__init__("ILLEGAL_TRANSITION", message)


class ValidationRequired(AppError):
    status_code = 422

    def __init__(self, message: str):
        super().__init__("VALIDATION_REQUIRED", message)


class NotFlagged(AppError):
    status_code = 409

    def __init__(self, message: str):
        super().__init__("NOT_FLAGGED", message)


class IntegrityStillFailing(AppError):
    status_code = 409

    def __init__(self, message: str):
        super().__init__("INTEGRITY_STILL_FAILING", message)


def _require_status(document: dict[str, Any], expected: DocumentStatus) -> None:
    if document["status"] != expected.value:
        raise IllegalTransition(
            f"document is {document['status']}, expected {expected.value} for this transition"
        )


async def _claim(
    db: AsyncIOMotorDatabase,
    document: dict[str, Any],
    expected: DocumentStatus,
    new: DocumentStatus,
) -> dict[str, Any]:
    """The authoritative, atomic status transition (D-023). `_require_status`
    above only gives a quick, descriptive error from the possibly-stale row the
    caller read; when two requests race, exactly one claim succeeds and the
    other gets this 409 *before* it writes anything else."""
    claimed = await documents_service.claim_status(
        db, document["_id"], expected=expected, new=new
    )
    if claimed is None:
        raise IllegalTransition(
            f"document was changed by another request and is no longer {expected.value}"
        )
    return claimed


async def _current_version(db: AsyncIOMotorDatabase, document: dict[str, Any]) -> dict[str, Any]:
    version = await versions_service.get_latest_version(db, document["_id"])
    if version is None:
        raise IllegalTransition("document has no version to operate on")
    return version


async def submit(
    db: AsyncIOMotorDatabase, *, document: dict[str, Any], actor: dict[str, Any]
) -> dict[str, Any]:
    """DRAFT -> SUBMITTED (current-version uploader only).

    Deliberately checks the *version's* uploader, not `document.owner_id`:
    an amendment or a changes-requested correction can be uploaded by
    someone other than the document's original owner (any DOCUMENT_AMEND
    role), and that's the person who should submit what they just
    uploaded (see DECISIONS.md D-016)."""
    _require_status(document, DocumentStatus.DRAFT)
    version = await _current_version(db, document)
    if str(version["uploaded_by"]) != str(actor["_id"]):
        raise IllegalTransition("only the current version's uploader may submit it")

    document_id = document["_id"]
    await _claim(db, document, DocumentStatus.DRAFT, DocumentStatus.SUBMITTED)
    # D-032: the uploader check above was made on a version read *before* the claim. If a
    # newer DRAFT landed in between, undo the claim (nothing else has been written yet)
    # rather than marking the stale version SUBMITTED.
    latest = await versions_service.get_latest_version(db, document_id)
    if latest is None or latest["_id"] != version["_id"]:
        await documents_service.claim_status(
            db, document_id, expected=DocumentStatus.SUBMITTED, new=DocumentStatus.DRAFT
        )
        raise IllegalTransition(
            "a newer version was uploaded while submitting; reload and submit the latest version"
        )
    await versions_service.update_status(db, version["_id"], VersionStatus.SUBMITTED)
    # A resubmission starts a fresh review; the previous comment no longer applies.
    await documents_service.set_review_feedback(db, document_id, comment=None)
    await audit.record(
        actor_id=actor["_id"],
        action="SUBMIT",
        target_type="document",
        target_id=document_id,
        result="SUCCESS",
    )
    return await documents_service.get_document_by_id(db, str(document_id))


async def review(
    db: AsyncIOMotorDatabase,
    *,
    document: dict[str, Any],
    actor: dict[str, Any],
    decision: str,
    comment: str | None,
) -> dict[str, Any]:
    """SUBMITTED -> UNDER_REVIEW, then either -> PENDING_APPROVAL or
    -> CHANGES_REQUESTED -> DRAFT, in one call (Reviewing Officer,
    reviewer != uploader)."""
    _require_status(document, DocumentStatus.SUBMITTED)
    if decision == "changes_requested" and not comment:
        raise ValidationRequired("a comment is required when requesting changes")
    if decision not in ("approve", "changes_requested"):  # pragma: no cover — Literal rejects this
        raise ValidationRequired(f"unknown review decision: {decision!r}")

    version = await _current_version(db, document)
    enforce_maker_checker(version["uploaded_by"], actor["_id"])

    document_id = document["_id"]
    await _claim(db, document, DocumentStatus.SUBMITTED, DocumentStatus.UNDER_REVIEW)
    await versions_service.update_status(db, version["_id"], VersionStatus.UNDER_REVIEW)
    await audit.record(
        actor_id=actor["_id"],
        action="REVIEW_START",
        target_type="document",
        target_id=document_id,
        result="SUCCESS",
    )

    if decision == "approve":
        await documents_service.update_status(db, document_id, DocumentStatus.PENDING_APPROVAL)
        await versions_service.update_status(db, version["_id"], VersionStatus.PENDING_APPROVAL)
        await audit.record(
            actor_id=actor["_id"],
            action="REVIEW_PASS",
            target_type="document",
            target_id=document_id,
            result="SUCCESS",
        )
    else:  # decision == "changes_requested" (validated above)
        await documents_service.update_status(db, document_id, DocumentStatus.CHANGES_REQUESTED)
        await versions_service.update_status(db, version["_id"], VersionStatus.CHANGES_REQUESTED)
        await audit.record(
            actor_id=actor["_id"],
            action="CHANGES_REQ",
            target_type="document",
            target_id=document_id,
            result="SUCCESS",
            meta={"comment": comment},
        )
        await documents_service.set_review_feedback(
            db, document_id, comment=comment, reviewer_id=actor["_id"]
        )
        # Plan Part 5: "->CHANGES_REQUESTED->DRAFT" — loops straight back.
        await documents_service.update_status(db, document_id, DocumentStatus.DRAFT)
        await versions_service.update_status(db, version["_id"], VersionStatus.DRAFT)

    return await documents_service.get_document_by_id(db, str(document_id))


async def promote_confirmed_anchor(
    db: AsyncIOMotorDatabase,
    *,
    document: dict[str, Any],
    version: dict[str, Any],
    anchor_doc: dict[str, Any],
    block_number: int,
    actor_id: Any = "SYSTEM",
) -> dict[str, Any]:
    """APPROVED -> BLOCKCHAIN_ANCHORED -> ACTIVE once a tx is confirmed.
    Called synchronously by `approve()` when confirmation lands inside its
    own poll window, and by the optional worker (workers/anchor_confirmer.py)
    for anchors that were still PENDING when that window closed — either way
    the previously-ACTIVE version (if any, i.e. an amendment) is retained
    and only ever marked SUPERSEDED, never mutated (Guardrail #7)."""
    document_id = document["_id"]

    # Claim the PENDING -> CONFIRMED step: if a worker pass and approve()'s own
    # confirm loop both get here, only one promotes (no double ANCHOR_OK /
    # ACTIVATE) — D-023.
    if not await blockchain_service.mark_confirmed(db, anchor_doc["_id"], block_number):
        return await documents_service.get_document_by_id(db, str(document_id))
    return await complete_promotion(
        db, document=document, version=version, anchor_doc=anchor_doc, actor_id=actor_id
    )


async def complete_promotion(
    db: AsyncIOMotorDatabase,
    *,
    document: dict[str, Any],
    version: dict[str, Any],
    anchor_doc: dict[str, Any],
    actor_id: Any = "SYSTEM",
) -> dict[str, Any]:
    """Everything after the anchor is CONFIRMED. Every write is idempotent, so the worker
    can re-run it for a document a crash left APPROVED under an already-CONFIRMED anchor
    (REL-01, D-037 defect 6) — only a holder of the document's lease does that."""
    document_id = document["_id"]
    await versions_service.mark_confirmed_anchor(
        db,
        version["_id"],
        anchor_id=anchor_doc["_id"],
        status=VersionStatus.BLOCKCHAIN_ANCHORED,
    )
    await documents_service.update_status(db, document_id, DocumentStatus.BLOCKCHAIN_ANCHORED)
    await audit.record(
        actor_id=actor_id,
        action="ANCHOR_OK",
        target_type="version",
        target_id=version["_id"],
        result="SUCCESS",
        meta={"tx_hash": anchor_doc.get("tx_hash")},
    )

    await versions_service.update_status(db, version["_id"], VersionStatus.ACTIVE)
    await documents_service.set_current_version(db, document_id, version["_id"])
    await documents_service.update_status(db, document_id, DocumentStatus.ACTIVE)
    await documents_service.set_anchor_alert(db, document_id, False)
    await anchor_retry.clear(db, document_id)

    previous_active = await versions_service.find_active_version_excluding(
        db, document_id, exclude_version_id=version["_id"]
    )
    if previous_active is not None:
        await versions_service.update_status(
            db, previous_active["_id"], VersionStatus.SUPERSEDED
        )

    await audit.record(
        actor_id=actor_id,
        action="ACTIVATE",
        target_type="document",
        target_id=document_id,
        result="SUCCESS",
    )
    return await documents_service.get_document_by_id(db, str(document_id))


async def approve(
    db: AsyncIOMotorDatabase, *, document: dict[str, Any], actor: dict[str, Any]
) -> dict[str, Any]:
    """PENDING_APPROVAL -> APPROVED (Legal Officer, approver != uploader),
    then automatically enqueues + attempts to confirm the anchor for this
    version. Never raises on an anchor/RPC failure: the document simply
    stays APPROVED (pending anchor) with an alert flag, and the caller gets
    a 200 either way — anchoring success/failure is reported in the
    response, not as an HTTP error."""
    _require_status(document, DocumentStatus.PENDING_APPROVAL)
    version = await _current_version(db, document)
    enforce_maker_checker(version["uploaded_by"], actor["_id"])

    document_id = document["_id"]
    settings = get_settings()

    # Claim BEFORE anything touches the chain: of N simultaneous approvals
    # exactly one gets past this line, so exactly one anchor attempt is made
    # and no loser can record a false ANCHOR_FAIL (D-023).
    await _claim(db, document, DocumentStatus.PENDING_APPROVAL, DocumentStatus.APPROVED)
    await versions_service.update_status(db, version["_id"], VersionStatus.APPROVED)
    await audit.record(
        actor_id=actor["_id"],
        action="APPROVE",
        target_type="document",
        target_id=document_id,
        result="SUCCESS",
    )

    anchor_doc: dict[str, Any] | None = None
    for attempt in range(settings.ANCHOR_MAX_ATTEMPTS):
        anchor_doc = await blockchain_service.anchor_document_version(
            db,
            document_id=document_id,
            version_id=version["_id"],
            version_no=version["version_no"],
            sha256=version["sha256"],
            event_type=int(AnchorEventType.APPROVED),
        )
        if anchor_doc["status"] == AnchorStatus.PENDING.value:
            break
        if attempt + 1 < settings.ANCHOR_MAX_ATTEMPTS:
            await asyncio.sleep(settings.ANCHOR_RETRY_BACKOFF_SEC)

    assert anchor_doc is not None  # loop always runs >=1 iteration

    if anchor_doc["status"] != AnchorStatus.PENDING.value:
        # Every attempt failed to even send the tx (RPC down, etc.).
        # Document stays APPROVED (pending anchor); app remains usable; a
        # later retry (the optional worker, or a manual re-run) can pick it
        # up without disturbing anything already committed above.
        await documents_service.set_anchor_alert(db, document_id, True)
        _logger.warning(
            "workflow: ANCHOR_FAIL — tx could not be sent",
            extra={"document_id": str(document_id), "error": anchor_doc.get("error")},
        )
        await audit.record(
            actor_id=actor["_id"],
            action="ANCHOR_FAIL",
            target_type="version",
            target_id=version["_id"],
            result="FAILED",
            meta={"error": anchor_doc.get("error")},
        )
        # Hand over to the worker (REL-01). A failure retrying cannot fix is marked
        # permanent here, and audited, so it shows up for an admin straight away.
        decision = await anchor_retry.enqueue(
            db, document_id, error_code=anchor_doc.get("error")
        )
        if decision.permanent:
            await anchor_retry.audit_permanent_failure(version["_id"], decision.reason)
        refreshed_document = await documents_service.get_document_by_id(db, str(document_id))
        return {"document": refreshed_document, "version": version, "anchor": anchor_doc}

    # Tx sent — a bounded synchronous confirm attempt (Hardhat/most Sepolia
    # blocks land well inside this window). If it doesn't land in time, the
    # anchor simply stays PENDING and the document stays APPROVED; nothing
    # here blocks indefinitely or fails the request.
    receipt = None
    for _ in range(settings.ANCHOR_CONFIRM_POLL_ATTEMPTS):
        receipt = await chain.confirm_tx(anchor_doc["tx_hash"])
        if receipt is not None:
            break
        await asyncio.sleep(settings.ANCHOR_CONFIRM_POLL_INTERVAL_SEC)

    if receipt is None:
        refreshed_document = await documents_service.get_document_by_id(db, str(document_id))
        return {"document": refreshed_document, "version": version, "anchor": anchor_doc}

    if receipt["status"] != 1:
        reverted_here = await blockchain_service.fail_pending(db, anchor_doc["_id"], REVERTED)
        await documents_service.set_anchor_alert(db, document_id, True)
        if reverted_here:
            await anchor_retry.enqueue(db, document_id, error_code=REVERTED)
        _logger.warning(
            "workflow: ANCHOR_FAIL — transaction reverted",
            extra={"document_id": str(document_id), "tx_hash": anchor_doc.get("tx_hash")},
        )
        await audit.record(
            actor_id=actor["_id"],
            action="ANCHOR_FAIL",
            target_type="version",
            target_id=version["_id"],
            result="FAILED",
            meta={"error": REVERTED},
        )
        anchor_doc = {**anchor_doc, "status": AnchorStatus.FAILED.value}
        refreshed_document = await documents_service.get_document_by_id(db, str(document_id))
        return {"document": refreshed_document, "version": version, "anchor": anchor_doc}

    refreshed_document = await promote_confirmed_anchor(
        db,
        document=document,
        version=version,
        anchor_doc=anchor_doc,
        block_number=receipt["block_number"],
        actor_id=actor["_id"],
    )
    anchor_doc = {
        **anchor_doc,
        "status": AnchorStatus.CONFIRMED.value,
        "block_number": receipt["block_number"],
    }
    refreshed_version = await versions_service.get_version_by_id(db, str(version["_id"]))
    return {"document": refreshed_document, "version": refreshed_version, "anchor": anchor_doc}


async def request_amendment(
    db: AsyncIOMotorDatabase,
    *,
    document: dict[str, Any],
    actor: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    """ACTIVE -> AMENDMENT_REQUESTED (Legal Officer or Authorized Staff).
    The actual new version arrives via a follow-up upload
    (documents.service.create_next_version, wired to the amend_of form
    field on POST /documents)."""
    _require_status(document, DocumentStatus.ACTIVE)
    document_id = document["_id"]
    await _claim(db, document, DocumentStatus.ACTIVE, DocumentStatus.AMENDMENT_REQUESTED)
    await audit.record(
        actor_id=actor["_id"],
        action="AMEND_REQ",
        target_type="document",
        target_id=document_id,
        result="SUCCESS",
        meta={"reason": reason},
    )
    return await documents_service.get_document_by_id(db, str(document_id))


async def archive(
    db: AsyncIOMotorDatabase, *, document: dict[str, Any], actor: dict[str, Any]
) -> dict[str, Any]:
    """ACTIVE -> ARCHIVED (Administrator or Legal Officer). All versions and
    anchors are retained untouched; only the document's own status changes."""
    _require_status(document, DocumentStatus.ACTIVE)
    document_id = document["_id"]
    await _claim(db, document, DocumentStatus.ACTIVE, DocumentStatus.ARCHIVED)
    await audit.record(
        actor_id=actor["_id"],
        action="ARCHIVE",
        target_type="document",
        target_id=document_id,
        result="SUCCESS",
    )
    return await documents_service.get_document_by_id(db, str(document_id))


async def clear_integrity_flag(
    db: AsyncIOMotorDatabase,
    *,
    document: dict[str, Any],
    actor: dict[str, Any],
    reason: str,
) -> list[int]:
    """Admin-only, audited removal of a TAMPERED or UNCONFIRMED flag (D-025, D-049). It cannot be
    used to hide a real mismatch: every anchored version is re-verified now,
    through the real 3-way verification, and the flag is cleared only if all
    of them return VERIFIED. Returns the version numbers that were verified."""
    from app.modules.verify import service as verify_service  # avoids an import cycle

    if document.get("integrity_flag") not in documents_service.CLEARABLE_INTEGRITY_FLAGS:
        raise NotFlagged("this document has no integrity flag to clear")

    document_id = document["_id"]
    baseline_updated_at = document["updated_at"]
    anchored = [
        v
        for v in await versions_service.list_versions_for_document(db, document_id)
        if v.get("anchored")
    ]

    outcomes: list[tuple[int, str]] = []
    for version in anchored:
        try:
            verdict = await verify_service.verify_version(
                db, version_id=str(version["_id"]), actor=actor
            )
            outcomes.append((version["version_no"], verdict.result))
        except AppError:  # storage unreachable etc. — not VERIFIED, so not clearable
            outcomes.append((version["version_no"], "UNVERIFIABLE"))

    failing = [{"version_no": n, "result": r} for n, r in outcomes if r != "VERIFIED"]
    if not anchored:
        failing = [{"version_no": None, "result": "NO_ANCHORED_VERSION"}]
    if failing:
        await audit.record(
            actor_id=actor["_id"],
            action="INTEGRITY_CLEAR_REFUSED",
            target_type="document",
            target_id=document_id,
            result="REFUSED",
            meta={"reason": reason, "failing": failing},
        )
        # "Could not check" is spelled out so it is never read as a pass or as a verdict (D-049).
        could_not_check = {"UNVERIFIABLE", "CHAIN_UNREACHABLE"}
        summary = ", ".join(
            (f"v{f['version_no']}: {f['result']}" if f["version_no"] else f["result"])
            + (" (unable to verify)" if f["result"] in could_not_check else "")
            for f in failing
        )
        raise IntegrityStillFailing(
            f"verification still fails ({summary}); the flag cannot be cleared"
        )

    cleared = await documents_service.clear_integrity_flag(
        db,
        document_id,
        expected_updated_at=baseline_updated_at,
        cleared_by=actor["_id"],
        reason=reason,
    )
    if not cleared:
        raise IllegalTransition("the document changed while it was being verified; retry")

    verified = sorted(n for n, _ in outcomes)
    await audit.record(
        actor_id=actor["_id"],
        action="INTEGRITY_CLEARED",
        target_type="document",
        target_id=document_id,
        result="SUCCESS",
        meta={"reason": reason, "verified_versions": verified},
    )
    return verified
