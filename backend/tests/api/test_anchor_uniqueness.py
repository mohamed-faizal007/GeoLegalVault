"""D-023: a version can have at most one live (PENDING/CONFIRMED) anchor row,
and PENDING -> CONFIRMED is claimed once, so promotion happens once."""

import asyncio
from datetime import UTC, datetime

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.modules.blockchain import service as blockchain_service
from app.modules.documents import workflow

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _anchor_row(version_id: ObjectId, document_id: ObjectId, **overrides) -> dict:
    row = {
        "document_id": document_id,
        "version_id": version_id,
        "sha256": "ab" * 32,
        "event_type": 1,
        "contract_address": "0xabc",
        "network": "sepolia",
        "block_number": None,
        "status": "PENDING",
        "live": True,
        "error": None,
        "created_at": datetime.now(UTC),
        "confirmed_at": None,
    }
    row.update(overrides)
    return row


async def test_database_refuses_a_second_live_anchor_for_the_same_version(db):
    version_id, document_id = ObjectId(), ObjectId()
    await db["blockchain_anchors"].insert_one(
        _anchor_row(version_id, document_id, tx_hash="0x" + "11" * 32)
    )
    with pytest.raises(DuplicateKeyError):
        await db["blockchain_anchors"].insert_one(
            _anchor_row(version_id, document_id, tx_hash="0x" + "22" * 32)
        )


async def test_failed_attempts_do_not_count_as_live_and_may_repeat(db):
    version_id, document_id = ObjectId(), ObjectId()
    for _ in range(3):  # the retry loop records one FAILED row per attempt
        await db["blockchain_anchors"].insert_one(
            _anchor_row(version_id, document_id, status="FAILED", live=False)
        )
    # ...and a live anchor can still follow them.
    await db["blockchain_anchors"].insert_one(
        _anchor_row(version_id, document_id, tx_hash="0x" + "33" * 32)
    )
    assert await db["blockchain_anchors"].count_documents({"version_id": version_id}) == 4


async def test_create_pending_anchor_returns_the_existing_live_row_instead_of_duplicating(db):
    version_id, document_id = ObjectId(), ObjectId()
    first = await blockchain_service.create_pending_anchor(
        db,
        document_id=document_id,
        version_id=version_id,
        sha256="ab" * 32,
        event_type=1,
        tx_hash="0x" + "44" * 32,
    )
    second = await blockchain_service.create_pending_anchor(
        db,
        document_id=document_id,
        version_id=version_id,
        sha256="ab" * 32,
        event_type=1,
        tx_hash="0x" + "55" * 32,
    )
    assert second["_id"] == first["_id"]
    assert await db["blockchain_anchors"].count_documents({"version_id": version_id}) == 1


async def test_mark_failed_clears_live_so_the_version_can_be_anchored_again(db):
    version_id, document_id = ObjectId(), ObjectId()
    first = await blockchain_service.create_pending_anchor(
        db,
        document_id=document_id,
        version_id=version_id,
        sha256="ab" * 32,
        event_type=1,
        tx_hash="0x" + "66" * 32,
    )
    await blockchain_service.mark_failed(db, first["_id"], "REVERTED")
    again = await blockchain_service.create_pending_anchor(
        db,
        document_id=document_id,
        version_id=version_id,
        sha256="ab" * 32,
        event_type=1,
        tx_hash="0x" + "77" * 32,
    )
    assert again["_id"] != first["_id"]


async def test_mark_confirmed_is_claimed_exactly_once(db):
    anchor = await blockchain_service.create_pending_anchor(
        db,
        document_id=ObjectId(),
        version_id=ObjectId(),
        sha256="ab" * 32,
        event_type=1,
        tx_hash="0x" + "88" * 32,
    )
    results = await asyncio.gather(
        *[blockchain_service.mark_confirmed(db, anchor["_id"], 7) for _ in range(5)]
    )
    assert sorted(results) == [False] * 4 + [True]


async def test_promote_confirmed_anchor_runs_once_when_called_concurrently(db):
    """A worker pass and approve()'s own confirm loop can both reach
    promote_confirmed_anchor for the same anchor; only one may promote."""
    document_id, version_id = ObjectId(), ObjectId()
    now = datetime.now(UTC)
    await db["documents"].insert_one(
        {
            "_id": document_id,
            "title": "t",
            "doc_type": "C",
            "classification": "X",
            "owner_id": ObjectId(),
            "status": "APPROVED",
            "current_version_id": None,
            "tags": [],
            "created_at": now,
            "updated_at": now,
            "anchor_pending_alert": False,
        }
    )
    await db["document_versions"].insert_one(
        {
            "_id": version_id,
            "document_id": document_id,
            "version_no": 1,
            "sha256": "ab" * 32,
            "storage_key": "k",
            "size_bytes": 1,
            "mime": "application/pdf",
            "status": "APPROVED",
            "uploaded_by": ObjectId(),
            "uploaded_at": now,
            "anchored": False,
            "anchor_id": None,
        }
    )
    anchor = await blockchain_service.create_pending_anchor(
        db,
        document_id=document_id,
        version_id=version_id,
        sha256="ab" * 32,
        event_type=1,
        tx_hash="0x" + "99" * 32,
    )
    document = await db["documents"].find_one({"_id": document_id})
    version = await db["document_versions"].find_one({"_id": version_id})

    await asyncio.gather(
        *[
            workflow.promote_confirmed_anchor(
                db, document=document, version=version, anchor_doc=anchor, block_number=5
            )
            for _ in range(4)
        ]
    )

    rows = await db["audit_logs"].find(
        {"target_id": {"$in": [document_id, version_id]}}
    ).to_list(None)
    actions = [r["action"] for r in rows]
    assert actions.count("ANCHOR_OK") == 1
    assert actions.count("ACTIVATE") == 1
    assert (await db["documents"].find_one({"_id": document_id}))["status"] == "ACTIVE"
