"""Real concurrency tests for D-022..D-024 (REL-02 / REL-03).

Every test fires genuinely concurrent requests with `asyncio.gather` over the
ASGI client against the real Mongo, RustFS and a local Hardhat chain. The
handlers interleave at every Mongo/storage `await`, which is exactly where the
old check-then-write code raced, so these fail on the pre-fix code (verified
when the change was made: see DECISIONS.md D-022 outcome).

If a future change makes one of these flaky, that is a real signal — the
assertions are about invariants (one winner, one anchor row, stored bytes ==
recorded hash), not about timing.
"""

import asyncio
import hashlib

import pytest
from botocore.exceptions import ClientError
from bson import ObjectId

from app.modules.users.models import Role
from app.services import storage
from tests.integration.test_anchor import local_chain  # noqa: F401 (reused fixture)
from tests.integration.test_workflow import (
    PDF_BYTES,
    _auth,
    _create_user_and_login,
    _geo,
    _get_document,
    _get_versions,
    _review_approve,
    _setup_three_roles,
    _submit,
    _upload,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")

N = 6  # concurrent requests per race


async def _fence_id(db) -> str:
    fence = await db["geofences"].find_one({})
    return str(fence["_id"])


async def _audit_actions(db, target_id: ObjectId) -> list[str]:
    rows = await db["audit_logs"].find({"target_id": target_id}).sort("created_at", 1).to_list(None)
    return [r["action"] for r in rows]


async def _pending_approval(client, db):
    """A document in PENDING_APPROVAL plus two distinct approvers (neither is
    the uploader), so concurrent approvals come from different accounts."""
    uploader, reviewer, approver = await _setup_three_roles(client, db)
    fence = await _fence_id(db)
    approver2 = await _create_user_and_login(
        client, db, email="approver2@example.com", role=Role.LEGAL_OFFICER, fence_id=fence
    )
    upload = await _upload(client, uploader)
    document_id = upload["document_id"]
    await _submit(client, uploader, document_id)
    await _review_approve(client, reviewer, document_id)
    return {
        "uploader": uploader,
        "reviewer": reviewer,
        "approvers": (approver, approver2),
        "document_id": document_id,
        "version_id": upload["version_id"],
        "fence": fence,
    }


async def test_concurrent_approvals_produce_one_winner_one_anchor_no_false_failures(
    client, db, local_chain  # noqa: F811
):
    ctx = await _pending_approval(client, db)
    document_id, version_id = ctx["document_id"], ctx["version_id"]
    a1, a2 = ctx["approvers"]

    responses = await asyncio.gather(
        *[
            client.post(
                f"/api/v1/documents/{document_id}/approve",
                headers={**_auth((a1, a2)[i % 2]), **_geo()},
            )
            for i in range(N)
        ]
    )

    codes = sorted(r.status_code for r in responses)
    assert codes == [200] + [409] * (N - 1), [r.text for r in responses]
    for loser in (r for r in responses if r.status_code == 409):
        assert loser.json()["error"]["code"] == "ILLEGAL_TRANSITION"
    winner = next(r for r in responses if r.status_code == 200).json()
    assert winner["status"] == "ACTIVE"
    assert winner["anchor_status"] == "CONFIRMED"

    anchors = await db["blockchain_anchors"].find(
        {"version_id": ObjectId(version_id)}
    ).to_list(None)
    assert len(anchors) == 1, anchors
    assert anchors[0]["status"] == "CONFIRMED"

    actions = await _audit_actions(db, ObjectId(document_id))
    assert actions.count("APPROVE") == 1
    assert actions.count("ACTIVATE") == 1
    assert "ANCHOR_FAIL" not in await _audit_actions(db, ObjectId(version_id))
    assert (await _audit_actions(db, ObjectId(version_id))).count("ANCHOR_OK") == 1

    document = await db["documents"].find_one({"_id": ObjectId(document_id)})
    assert document["status"] == "ACTIVE"
    assert document["anchor_pending_alert"] is False


async def test_concurrent_conflicting_reviews_record_exactly_one_decision(
    client, db, local_chain  # noqa: F811
):
    uploader, reviewer, _approver = await _setup_three_roles(client, db)
    reviewer2 = await _create_user_and_login(
        client,
        db,
        email="reviewer2@example.com",
        role=Role.REVIEWING_OFFICER,
        fence_id=await _fence_id(db),
    )
    upload = await _upload(client, uploader)
    document_id = upload["document_id"]
    await _submit(client, uploader, document_id)

    approve, changes = await asyncio.gather(
        client.post(
            f"/api/v1/documents/{document_id}/review",
            headers=_auth(reviewer),
            json={"decision": "approve"},
        ),
        client.post(
            f"/api/v1/documents/{document_id}/review",
            headers=_auth(reviewer2),
            json={"decision": "changes_requested", "comment": "needs a clause 4"},
        ),
    )

    assert sorted([approve.status_code, changes.status_code]) == [200, 409]
    actions = await _audit_actions(db, ObjectId(document_id))
    assert actions.count("REVIEW_START") == 1
    decisions = [a for a in actions if a in ("REVIEW_PASS", "CHANGES_REQ")]
    assert len(decisions) == 1

    document = await db["documents"].find_one({"_id": ObjectId(document_id)})
    if approve.status_code == 200:
        assert decisions == ["REVIEW_PASS"]
        assert document["status"] == "PENDING_APPROVAL"
        assert not document.get("review_feedback")
    else:
        assert decisions == ["CHANGES_REQ"]
        assert document["status"] == "DRAFT"
        assert document["review_feedback"]["comment"] == "needs a clause 4"


async def test_concurrent_double_submit_is_one_transition_and_one_audit_row(client, db):
    uploader, _reviewer, _approver = await _setup_three_roles(client, db)
    upload = await _upload(client, uploader)
    document_id = upload["document_id"]

    responses = await asyncio.gather(
        *[
            client.post(f"/api/v1/documents/{document_id}/submit", headers=_auth(uploader))
            for _ in range(N)
        ]
    )

    assert sorted(r.status_code for r in responses) == [200] + [409] * (N - 1)
    assert (await _audit_actions(db, ObjectId(document_id))).count("SUBMIT") == 1


async def test_submit_rolls_back_when_a_newer_version_lands_between_read_and_claim(
    client, db, monkeypatch
):
    """D-032: simulate the interleaving deterministically — a correction upload
    inserts V2 right after submit wins its claim. Submit must not mark the stale V1
    SUBMITTED; it undoes the claim and reports a conflict."""
    from app.modules.documents import service as documents_service
    from app.modules.documents import workflow

    uploader, _reviewer, _approver = await _setup_three_roles(client, db)
    upload = await _upload(client, uploader)
    document_id = upload["document_id"]
    await db["documents"].update_one(
        {"_id": ObjectId(document_id)},
        {"$set": {"review_feedback": {"comment": "fix", "reviewer_id": ObjectId()}}},
    )

    real_claim = workflow._claim

    async def claim_then_interleave(db_, document, expected, new):
        claimed = await real_claim(db_, document, expected, new)
        await documents_service.create_next_version(
            db_,
            document=document,
            actor_id=document["owner_id"],
            data=PDF_BYTES + b"-newer",
            content_type="application/pdf",
        )
        return claimed

    monkeypatch.setattr(workflow, "_claim", claim_then_interleave)

    resp = await client.post(f"/api/v1/documents/{document_id}/submit", headers=_auth(uploader))
    assert resp.status_code == 409, resp.text

    monkeypatch.setattr(workflow, "_claim", real_claim)
    row = await db["documents"].find_one({"_id": ObjectId(document_id)})
    assert row["status"] == "DRAFT"  # claim rolled back
    versions = await _get_versions(client, uploader, document_id)
    assert [(v["version_no"], v["status"]) for v in versions] == [(1, "DRAFT"), (2, "DRAFT")]
    assert "SUBMIT" not in await _audit_actions(db, ObjectId(document_id))

    # The user retries and submits the newer version, which is the one authorised.
    retry = await client.post(f"/api/v1/documents/{document_id}/submit", headers=_auth(uploader))
    assert retry.status_code == 200, retry.text
    versions = await _get_versions(client, uploader, document_id)
    assert [(v["version_no"], v["status"]) for v in versions] == [(1, "DRAFT"), (2, "SUBMITTED")]


# --- amendment uploads (REL-03) ---------------------------------------------


async def _active_document_with_amendment_requested(client, db):
    """ACTIVE V1 -> amendment requested, with two accounts allowed to upload
    the next version (both hold document:amend)."""
    uploader, reviewer, approver = await _setup_three_roles(client, db)
    fence = await _fence_id(db)
    staff2 = await _create_user_and_login(
        client, db, email="staff2@example.com", role=Role.AUTHORIZED_STAFF, fence_id=fence
    )
    upload = await _upload(client, uploader)
    document_id = upload["document_id"]
    await _submit(client, uploader, document_id)
    await _review_approve(client, reviewer, document_id)
    approved = await client.post(
        f"/api/v1/documents/{document_id}/approve", headers={**_auth(approver), **_geo()}
    )
    assert approved.json()["status"] == "ACTIVE", approved.text
    amend = await client.post(
        f"/api/v1/documents/{document_id}/amend",
        headers={**_auth(uploader), **_geo()},
        json={"reason": "fix clause 2"},
    )
    assert amend.status_code == 200, amend.text
    return {
        "uploader": uploader,
        "staff2": staff2,
        "reviewer": reviewer,
        "approver": approver,
        "document_id": document_id,
        "v1_sha": upload["sha256"],
        "v1_id": upload["version_id"],
    }


async def _post_amend_upload(client, token: str, document_id: str, data: bytes):
    return await client.post(
        "/api/v1/documents",
        headers={**_auth(token), **_geo()},
        data={
            "title": "Vendor NDA",
            "doc_type": "CONTRACT",
            "classification": "RESTRICTED",
            "amend_of": document_id,
        },
        files={"file": ("contract.pdf", data, "application/pdf")},
    )


def _object_exists(key: str) -> bool:
    try:
        storage.get_object(key)
    except ClientError:
        return False
    return True


async def test_concurrent_amendment_uploads_never_overwrite_and_hash_matches_stored_bytes(
    client, db, local_chain  # noqa: F811
):
    ctx = await _active_document_with_amendment_requested(client, db)
    document_id = ctx["document_id"]
    bytes_a = PDF_BYTES + b"-version-from-uploader-A"
    bytes_b = PDF_BYTES + b"-version-from-staff-B"

    resp_a, resp_b = await asyncio.gather(
        _post_amend_upload(client, ctx["uploader"], document_id, bytes_a),
        _post_amend_upload(client, ctx["staff2"], document_id, bytes_b),
    )

    assert sorted([resp_a.status_code, resp_b.status_code]) == [201, 409], (
        resp_a.text,
        resp_b.text,
    )
    winner_resp, loser_resp = (resp_a, resp_b) if resp_a.status_code == 201 else (resp_b, resp_a)
    a_won = resp_a.status_code == 201
    winner_bytes, loser_bytes = (bytes_a, bytes_b) if a_won else (bytes_b, bytes_a)
    winner_token = ctx["uploader"] if resp_a.status_code == 201 else ctx["staff2"]
    assert loser_resp.json()["error"]["code"] == "VERSION_CONFLICT"

    versions = await _get_versions(client, ctx["approver"], document_id)
    assert [v["version_no"] for v in versions] == [1, 2]
    v1, v2 = versions

    # The recorded hash is the winner's, and the object at the recorded key is
    # exactly the winner's bytes — never the loser's (REL-03).
    assert v2["sha256"] == hashlib.sha256(winner_bytes).hexdigest() == winner_resp.json()["sha256"]
    assert storage.get_object(v2["storage_key"]) == winner_bytes
    assert hashlib.sha256(storage.get_object(v2["storage_key"])).hexdigest() == v2["sha256"]
    # The loser's orphan was discarded and V1's object is untouched.
    loser_key = storage.build_version_key(
        document_id, 2, hashlib.sha256(loser_bytes).hexdigest()
    )
    assert not _object_exists(loser_key)
    assert hashlib.sha256(storage.get_object(v1["storage_key"])).hexdigest() == ctx["v1_sha"]

    # End to end: the version approves, anchors, and verifies cleanly — no false TAMPERED.
    await _submit(client, winner_token, document_id)
    await _review_approve(client, ctx["reviewer"], document_id)
    approved = await client.post(
        f"/api/v1/documents/{document_id}/approve", headers={**_auth(ctx["approver"]), **_geo()}
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "ACTIVE"
    verify = await client.post(f"/api/v1/verify/{v2['id']}", headers=_auth(ctx["approver"]))
    assert verify.json()["result"] == "VERIFIED"
    assert (await _get_document(client, ctx["approver"], document_id))["integrity_flag"] is None


async def _upload_audit_count(db, document_id: str, version_no: int) -> int:
    return await db["audit_logs"].count_documents(
        {"target_id": ObjectId(document_id), "action": "UPLOAD", "meta.version_no": version_no}
    )


async def test_concurrent_identical_amendment_upload_is_idempotent(
    client, db, local_chain  # noqa: F811
):
    """Three identical uploads at once. Whatever order they interleave in (a request that
    arrives after the first finished included, D-048), all are answered 201 with one version."""
    ctx = await _active_document_with_amendment_requested(client, db)
    document_id = ctx["document_id"]
    data = PDF_BYTES + b"-double-click"

    responses = await asyncio.gather(
        *[_post_amend_upload(client, ctx["uploader"], document_id, data) for _ in range(3)]
    )

    assert [r.status_code for r in responses] == [201, 201, 201]
    assert len({r.json()["version_id"] for r in responses}) == 1
    versions = await _get_versions(client, ctx["approver"], document_id)
    assert [v["version_no"] for v in versions] == [1, 2]
    assert storage.get_object(versions[1]["storage_key"]) == data
    # One accepted upload -> one UPLOAD audit row for it (replays are not re-audited).
    assert await _upload_audit_count(db, document_id, 2) == 1


async def test_late_identical_amendment_upload_replays_with_201(
    client, db, local_chain  # noqa: F811
):
    """The ordering that failed on CI, forced directly: the identical retry is sent only
    after the first upload has completed (the document is a plain DRAFT by then), D-048."""
    ctx = await _active_document_with_amendment_requested(client, db)
    document_id = ctx["document_id"]
    data = PDF_BYTES + b"-late-retry"

    first = await _post_amend_upload(client, ctx["uploader"], document_id, data)
    assert first.status_code == 201, first.text
    assert (await _get_document(client, ctx["approver"], document_id))["status"] == "DRAFT"

    late = await _post_amend_upload(client, ctx["uploader"], document_id, data)
    assert late.status_code == 201, late.text
    assert late.json() == first.json()

    versions = await _get_versions(client, ctx["approver"], document_id)
    assert [v["version_no"] for v in versions] == [1, 2]
    assert storage.get_object(versions[1]["storage_key"]) == data
    assert await _upload_audit_count(db, document_id, 2) == 1


async def _assert_rejected_and_unchanged(client, ctx, response, *, expect_status: str):
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "ILLEGAL_TRANSITION"
    versions = await _get_versions(client, ctx["approver"], ctx["document_id"])
    assert [v["version_no"] for v in versions] == [1, 2]
    document = await _get_document(client, ctx["approver"], ctx["document_id"])
    assert document["status"] == expect_status


async def test_late_replay_is_refused_for_another_uploader(client, db, local_chain):  # noqa: F811
    ctx = await _active_document_with_amendment_requested(client, db)
    data = PDF_BYTES + b"-mine"
    first = await _post_amend_upload(client, ctx["uploader"], ctx["document_id"], data)
    assert first.status_code == 201, first.text

    # Same bytes, but not the user who uploaded that version: no replay, no leak of the version.
    other = await _post_amend_upload(client, ctx["staff2"], ctx["document_id"], data)
    await _assert_rejected_and_unchanged(client, ctx, other, expect_status="DRAFT")
    assert "version_id" not in other.text


async def test_late_replay_is_refused_for_different_bytes(client, db, local_chain):  # noqa: F811
    ctx = await _active_document_with_amendment_requested(client, db)
    first = await _post_amend_upload(
        client, ctx["uploader"], ctx["document_id"], PDF_BYTES + b"-first"
    )
    assert first.status_code == 201, first.text

    different = await _post_amend_upload(
        client, ctx["uploader"], ctx["document_id"], PDF_BYTES + b"-second"
    )
    await _assert_rejected_and_unchanged(client, ctx, different, expect_status="DRAFT")


async def test_late_replay_is_refused_once_the_version_is_submitted(
    client, db, local_chain  # noqa: F811
):
    ctx = await _active_document_with_amendment_requested(client, db)
    data = PDF_BYTES + b"-then-submitted"
    first = await _post_amend_upload(client, ctx["uploader"], ctx["document_id"], data)
    assert first.status_code == 201, first.text
    await _submit(client, ctx["uploader"], ctx["document_id"])
    submitted_status = (await _get_document(client, ctx["approver"], ctx["document_id"]))["status"]
    assert submitted_status != "DRAFT"

    retry = await _post_amend_upload(client, ctx["uploader"], ctx["document_id"], data)
    await _assert_rejected_and_unchanged(client, ctx, retry, expect_status=submitted_status)


async def test_late_replay_cannot_touch_an_active_document(client, db, local_chain):  # noqa: F811
    ctx = await _active_document_with_amendment_requested(client, db)
    data = PDF_BYTES + b"-goes-live"
    first = await _post_amend_upload(client, ctx["uploader"], ctx["document_id"], data)
    assert first.status_code == 201, first.text
    await _submit(client, ctx["uploader"], ctx["document_id"])
    await _review_approve(client, ctx["reviewer"], ctx["document_id"])
    approved = await client.post(
        f"/api/v1/documents/{ctx['document_id']}/approve",
        headers={**_auth(ctx["approver"]), **_geo()},
    )
    assert approved.json()["status"] == "ACTIVE", approved.text

    retry = await _post_amend_upload(client, ctx["uploader"], ctx["document_id"], data)
    await _assert_rejected_and_unchanged(client, ctx, retry, expect_status="ACTIVE")


async def test_amend_of_a_fresh_first_upload_is_never_a_replay(client, db):
    """A never-submitted v1 DRAFT does not accept amendments (D-015) even with identical
    bytes from its own uploader: the replay rule needs an amendment version (>= V2)."""
    uploader, _reviewer, approver = await _setup_three_roles(client, db)
    upload = await _upload(client, uploader)

    again = await _post_amend_upload(client, uploader, upload["document_id"], PDF_BYTES)

    assert again.status_code == 409, again.text
    assert again.json()["error"]["code"] == "ILLEGAL_TRANSITION"
    versions = await _get_versions(client, approver, upload["document_id"])
    assert [v["version_no"] for v in versions] == [1]


async def test_stale_amendment_request_never_becomes_a_second_version(
    client, db, local_chain  # noqa: F811
):
    """Deterministic form of the race behind D-029: a request that validated
    AMENDMENT_REQUESTED on a stale document row must not build V(n+2) on top of
    the version an identical/competing request already created."""
    from app.modules.documents import service as documents_service

    ctx = await _active_document_with_amendment_requested(client, db)
    document_id = ctx["document_id"]
    stale_document = await db["documents"].find_one({"_id": ObjectId(document_id)})
    assert stale_document["status"] == "AMENDMENT_REQUESTED"
    data = PDF_BYTES + b"-winner"

    winner = await _post_amend_upload(client, ctx["uploader"], document_id, data)
    assert winner.status_code == 201, winner.text
    uploader_id = (await _get_versions(client, ctx["approver"], document_id))[1]["uploaded_by"]

    # Same bytes, same uploader, stale row -> replay of the winner, no V3.
    replay = await documents_service.create_next_version(
        db,
        document=stale_document,
        actor_id=ObjectId(uploader_id),
        data=data,
        content_type="application/pdf",
    )
    assert replay["replayed"] is True
    assert str(replay["version"]["_id"]) == winner.json()["version_id"]

    # Different bytes on the same stale row -> conflict, no V3 either.
    with pytest.raises(documents_service.VersionConflict):
        await documents_service.create_next_version(
            db,
            document=stale_document,
            actor_id=ObjectId(uploader_id),
            data=PDF_BYTES + b"-someone-else",
            content_type="application/pdf",
        )
    versions = await _get_versions(client, ctx["approver"], document_id)
    assert [v["version_no"] for v in versions] == [1, 2]


async def test_identical_reupload_in_the_correction_case_is_a_replay_not_a_new_draft(client, db):
    from app.modules.documents import service as documents_service

    uploader, _reviewer, _approver = await _setup_three_roles(client, db)
    upload = await _upload(client, uploader)
    document_id = upload["document_id"]
    # DRAFT with changes requested (what a review leaves behind).
    await db["documents"].update_one(
        {"_id": ObjectId(document_id)},
        {"$set": {"review_feedback": {"comment": "fix", "reviewer_id": ObjectId()}}},
    )
    document = await db["documents"].find_one({"_id": ObjectId(document_id)})
    owner = document["owner_id"]
    corrected = PDF_BYTES + b"-corrected"

    first = await documents_service.create_next_version(
        db, document=document, actor_id=owner, data=corrected, content_type="application/pdf"
    )
    assert first["version"]["version_no"] == 2 and not first.get("replayed")

    again = await documents_service.create_next_version(
        db, document=document, actor_id=owner, data=corrected, content_type="application/pdf"
    )
    assert again["replayed"] is True
    assert again["version"]["_id"] == first["version"]["_id"]
    count = await db["document_versions"].count_documents({"document_id": ObjectId(document_id)})
    assert count == 2

    # A genuinely different correction is still a new version.
    third = await documents_service.create_next_version(
        db,
        document=document,
        actor_id=owner,
        data=PDF_BYTES + b"-corrected-again",
        content_type="application/pdf",
    )
    assert third["version"]["version_no"] == 3


async def test_storage_key_is_content_addressed_so_different_bytes_never_collide():
    doc = str(ObjectId())
    h1 = hashlib.sha256(b"one").hexdigest()
    h2 = hashlib.sha256(b"two").hexdigest()
    assert storage.build_version_key(doc, 2, h1) != storage.build_version_key(doc, 2, h2)
    assert storage.build_version_key(doc, 2, h1) == storage.build_version_key(doc, 2, h1)
    assert storage.build_version_key(doc, 1, h1) != storage.build_version_key(doc, 2, h1)
