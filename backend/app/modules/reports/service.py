"""reports module service layer — simple Mongo aggregations for the admin
reporting dashboard (Plan Part 16, Phase 10). Read-only: this module never
writes anything, it only summarizes what other modules already recorded.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.clearance import visible_classifications
from app.modules.audit.models import AUDIT_LOGS_COLLECTION
from app.modules.blockchain.models import BLOCKCHAIN_ANCHORS_COLLECTION, AnchorStatus
from app.modules.documents.models import DOCUMENTS_COLLECTION
from app.modules.reports.schemas import (
    AnchoringStats,
    DocTypeCount,
    ReportsSummary,
    StatusCount,
    VerificationStats,
)
from app.modules.verify.models import VERIFICATION_RECORDS_COLLECTION, VerificationResult
from app.modules.versions.models import DOCUMENT_VERSIONS_COLLECTION

# "Recent" verifications is a bounded window rather than all-time, so the
# figure stays meaningful as verification_records grows over the vault's
# lifetime — 30 days is a reasonable default for a prototype's dashboard.
VERIFICATIONS_WINDOW_DAYS = 30


async def _group_counts(
    db: AsyncIOMotorDatabase,
    collection: str,
    field: str,
    match: dict[str, Any] | None = None,
) -> dict[str, int]:
    pipeline: list[dict[str, Any]] = [{"$match": match}] if match else []
    pipeline.append({"$group": {"_id": f"${field}", "count": {"$sum": 1}}})
    cursor = db[collection].aggregate(pipeline)
    return {doc["_id"]: doc["count"] async for doc in cursor if doc["_id"] is not None}


async def get_summary(db: AsyncIOMotorDatabase, viewer: dict[str, Any]) -> ReportsSummary:
    """Counts over the documents the viewer may see (D-051). No "N hidden" hint: a number
    would itself reveal that documents above the viewer's clearance exist."""
    allowed = visible_classifications(viewer)
    visible_docs = {"classification": {"$in": allowed}}
    # Hidden = anything not at an allowed level (including a missing or unknown value).
    hidden_doc_ids = [
        d["_id"]
        async for d in db[DOCUMENTS_COLLECTION].find(
            {"classification": {"$nin": allowed}}, {"_id": 1}
        )
    ]
    hidden_version_ids = (
        [
            v["_id"]
            async for v in db[DOCUMENT_VERSIONS_COLLECTION].find(
                {"document_id": {"$in": hidden_doc_ids}}, {"_id": 1}
            )
        ]
        if hidden_doc_ids
        else []
    )
    status_counts = await _group_counts(db, DOCUMENTS_COLLECTION, "status", visible_docs)
    documents_by_status = [
        StatusCount(status=status, count=count)
        for status, count in sorted(status_counts.items())
    ]

    doc_type_counts = await _group_counts(db, DOCUMENTS_COLLECTION, "doc_type", visible_docs)
    documents_by_doc_type = [
        DocTypeCount(doc_type=doc_type, count=count)
        for doc_type, count in sorted(doc_type_counts.items())
    ]

    anchor_counts = await _group_counts(
        db, BLOCKCHAIN_ANCHORS_COLLECTION, "status", {"document_id": {"$nin": hidden_doc_ids}}
    )
    confirmed = anchor_counts.get(AnchorStatus.CONFIRMED.value, 0)
    failed = anchor_counts.get(AnchorStatus.FAILED.value, 0)
    pending = anchor_counts.get(AnchorStatus.PENDING.value, 0)
    decided = confirmed + failed
    anchoring = AnchoringStats(
        pending=pending,
        confirmed=confirmed,
        failed=failed,
        success_rate=(confirmed / decided) if decided else 0.0,
    )

    since = datetime.now(UTC) - timedelta(days=VERIFICATIONS_WINDOW_DAYS)
    verify_cursor = db[VERIFICATION_RECORDS_COLLECTION].aggregate(
        [
            {
                "$match": {
                    "created_at": {"$gte": since},
                    "version_id": {"$nin": hidden_version_ids},
                }
            },
            {"$group": {"_id": "$result", "count": {"$sum": 1}}},
        ]
    )
    verify_counts = {doc["_id"]: doc["count"] async for doc in verify_cursor}
    verifications_recent = VerificationStats(
        verified=verify_counts.get(VerificationResult.VERIFIED.value, 0),
        mismatch=verify_counts.get(VerificationResult.MISMATCH.value, 0),
        not_anchored=verify_counts.get(VerificationResult.NOT_ANCHORED.value, 0),
        anchor_missing=verify_counts.get(VerificationResult.ANCHOR_MISSING.value, 0),
        file_missing=verify_counts.get(VerificationResult.FILE_MISSING.value, 0),
        chain_unreachable=verify_counts.get(VerificationResult.CHAIN_UNREACHABLE.value, 0),
        window_days=VERIFICATIONS_WINDOW_DAYS,
    )

    geofence_denied_count = await db[AUDIT_LOGS_COLLECTION].count_documents(
        {"action": "GEOFENCE_DENIED"}
    )

    return ReportsSummary(
        documents_by_status=documents_by_status,
        documents_by_doc_type=documents_by_doc_type,
        anchoring=anchoring,
        verifications_recent=verifications_recent,
        geofence_denied_count=geofence_denied_count,
    )
