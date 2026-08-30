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
from app.modules.blockchain import service as blockchain_service
from app.modules.blockchain.models import AnchorEventType, AnchorStatus
from app.modules.documents import service as documents_service
from app.modules.documents.models import DocumentStatus
from app.modules.versions import service as versions_service
from app.modules.versions.models import VersionStatus
from app.services import blockchain as chain

_logger = logging.getLogger(__name__)


class IllegalTransition(AppError):
    status_code = 409

    def __init__(self, message: str):
        super().__init__("ILLEGAL_TRANSITION", message)


class ValidationRequired(AppError):
    status_code = 422

    def __init__(self, message: str):
        super().__init__("VALIDATION_REQUIRED", message)


def _require_status(document: dict[str, Any], expected: DocumentStatus) -> None:
    if document["status"] != expected.value:
        raise IllegalTransition(
            f"document is {document['status']}, expected {expected.value} for this transition"
        )


async def _current_version(db: AsyncIOMotorDatabase, document: dict[str, Any]) -> dict[str, Any]:
    version = await versions_service.get_latest_version(db, document["_id"])
    if version is None:
        raise IllegalTransition("document has no version to operate on")
    return version


async def submit(
    db: AsyncIOMotorDatabase, *, document: dict[str, Any], actor: dict[str, Any]
) -> dict[str, Any]:
    """DRAFT -> SUBMITTED (owner only)."""
    _require_status(document, DocumentStatus.DRAFT)
    if str(document["owner_id"]) != str(actor["_id"]):
        raise IllegalTransition("only the document's owner may submit it")

    version = await _current_version(db, document)
    document_id = document["_id"]
    await documents_service.update_status(db, document_id, DocumentStatus.SUBMITTED)
    await versions_service.update_status(db, version["_id"], VersionStatus.SUBMITTED)
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
    await documents_service.update_status(db, document_id, DocumentStatus.UNDER_REVIEW)
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

    await blockchain_service.mark_confirmed(db, anchor_doc["_id"], block_number)
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
        meta={"tx_hash": anchor_doc["tx_hash"]},
    )

    await versions_service.update_status(db, version["_id"], VersionStatus.ACTIVE)
    await documents_service.set_current_version(db, document_id, version["_id"])
    await documents_service.update_status(db, document_id, DocumentStatus.ACTIVE)
    await documents_service.set_anchor_alert(db, document_id, False)

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

    await documents_service.update_status(db, document_id, DocumentStatus.APPROVED)
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
        await blockchain_service.mark_failed(db, anchor_doc["_id"], "transaction reverted")
        await documents_service.set_anchor_alert(db, document_id, True)
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
            meta={"error": "transaction reverted"},
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
    await documents_service.update_status(db, document_id, DocumentStatus.AMENDMENT_REQUESTED)
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
    await documents_service.update_status(db, document_id, DocumentStatus.ARCHIVED)
    await audit.record(
        actor_id=actor["_id"],
        action="ARCHIVE",
        target_type="document",
        target_id=document_id,
        result="SUCCESS",
    )
    return await documents_service.get_document_by_id(db, str(document_id))
