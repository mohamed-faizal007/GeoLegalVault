"""Integration tests for the lifecycle state machine (Plan Part 5):
submit -> review -> approve(+anchor) -> amend -> archive.

Reuses the real local Hardhat node fixture from test_anchor.py for the
happy-path and amendment tests (genuine sign -> send -> mine -> confirm
cycle, not mocked); the anchor-failure test monkeypatches the RPC call
itself, so it needs no chain at all.
"""

import hashlib

import pytest

from app.services import blockchain as chain
from tests.integration.test_anchor import local_chain  # noqa: F401 (reused fixture)

pytestmark = pytest.mark.asyncio(loop_scope="session")

HQ_RING = [
    [78.14, 11.66],
    [78.16, 11.66],
    [78.16, 11.68],
    [78.14, 11.68],
    [78.14, 11.66],
]
INSIDE_HEADERS = {"X-Geo-Lat": "11.67", "X-Geo-Lng": "78.15", "X-Geo-Accuracy": "10"}

PDF_BYTES = b"%PDF-1.4\n%mock pdf content for testing\n" + b"A" * 200
PDF_BYTES_V2 = b"%PDF-1.4\n%mock pdf content for testing, corrected\n" + b"B" * 200

PASSWORD = "Str0ngPassw0rd!"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _ts_header() -> dict:
    import time

    return {"X-Geo-Timestamp": str(time.time())}


def _geo(**overrides) -> dict:
    return {**INSIDE_HEADERS, **_ts_header(), **overrides}


async def _create_fence(db) -> str:
    from app.modules.geofences.schemas import GeofenceCreate, GeoJSONPolygon
    from app.modules.geofences.service import create_geofence

    fence = await create_geofence(
        db, GeofenceCreate(name="HQ", region=GeoJSONPolygon(coordinates=[HQ_RING]))
    )
    return fence.id


async def _create_user_and_login(client, db, *, email: str, role, fence_id: str) -> str:
    from app.modules.users.schemas import UserCreate
    from app.modules.users.service import create_user

    await create_user(
        db,
        UserCreate(
            email=email, password=PASSWORD, name=email, role=role, assigned_geofence_ids=[fence_id]
        ),
    )
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _upload(client, token: str, *, title="Vendor NDA", data=PDF_BYTES, amend_of=None) -> dict:
    form = {
        "title": title,
        "doc_type": "CONTRACT",
        "classification": "RESTRICTED",
        "tags": "nda,vendor",
    }
    if amend_of:
        form["amend_of"] = amend_of
    resp = await client.post(
        "/api/v1/documents",
        headers={**_auth(token), **_geo()},
        data=form,
        files={"file": ("contract.pdf", data, "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _submit(client, token: str, document_id: str) -> dict:
    resp = await client.post(
        f"/api/v1/documents/{document_id}/submit", headers=_auth(token)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _review_approve(client, token: str, document_id: str) -> dict:
    resp = await client.post(
        f"/api/v1/documents/{document_id}/review",
        headers=_auth(token),
        json={"decision": "approve"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _get_document(client, token: str, document_id: str) -> dict:
    resp = await client.get(f"/api/v1/documents/{document_id}", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _get_versions(client, token: str, document_id: str) -> list[dict]:
    resp = await client.get(f"/api/v1/documents/{document_id}/versions", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


async def _setup_three_roles(client, db):
    """Uploader (Authorized Staff), Reviewer (Reviewing Officer), Approver
    (Legal Officer) — the normal, fully-separated happy path."""
    from app.modules.users.models import Role

    fence_id = await _create_fence(db)
    uploader_token = await _create_user_and_login(
        client, db, email="uploader@example.com", role=Role.AUTHORIZED_STAFF, fence_id=fence_id
    )
    reviewer_token = await _create_user_and_login(
        client, db, email="reviewer@example.com", role=Role.REVIEWING_OFFICER, fence_id=fence_id
    )
    approver_token = await _create_user_and_login(
        client, db, email="approver@example.com", role=Role.LEGAL_OFFICER, fence_id=fence_id
    )
    return uploader_token, reviewer_token, approver_token


async def test_happy_path_draft_to_active_with_real_anchor(client, db, local_chain):  # noqa: F811
    uploader, reviewer, approver = await _setup_three_roles(client, db)

    upload = await _upload(client, uploader)
    document_id = upload["document_id"]
    assert upload["status"] == "DRAFT"

    submitted = await _submit(client, uploader, document_id)
    assert submitted["status"] == "SUBMITTED"

    reviewed = await _review_approve(client, reviewer, document_id)
    assert reviewed["status"] == "PENDING_APPROVAL"

    resp = await client.post(
        f"/api/v1/documents/{document_id}/approve", headers={**_auth(approver), **_geo()}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ACTIVE"
    assert body["anchor_status"] == "CONFIRMED"
    assert body["tx_hash"] is not None and body["tx_hash"].startswith("0x")

    document = await _get_document(client, approver, document_id)
    assert document["status"] == "ACTIVE"
    assert document["current_version_id"] == upload["version_id"]

    versions = await _get_versions(client, approver, document_id)
    assert len(versions) == 1
    assert versions[0]["status"] == "ACTIVE"
    assert versions[0]["anchored"] is True
    assert versions[0]["anchor_id"] is not None

    onchain = await chain.get_onchain_anchor(document_id, 1)
    assert onchain["exists"] is True
    assert onchain["hash"] == "0x" + hashlib.sha256(PDF_BYTES).hexdigest()


async def test_approver_cannot_be_uploader(client, db, local_chain):  # noqa: F811
    from app.modules.users.models import Role

    fence_id = await _create_fence(db)
    legal_officer = await _create_user_and_login(
        client, db, email="lo@example.com", role=Role.LEGAL_OFFICER, fence_id=fence_id
    )
    reviewer = await _create_user_and_login(
        client, db, email="rev@example.com", role=Role.REVIEWING_OFFICER, fence_id=fence_id
    )

    upload = await _upload(client, legal_officer)
    document_id = upload["document_id"]
    await _submit(client, legal_officer, document_id)
    await _review_approve(client, reviewer, document_id)

    resp = await client.post(
        f"/api/v1/documents/{document_id}/approve",
        headers={**_auth(legal_officer), **_geo()},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "MAKER_CHECKER_VIOLATION"

    # The app stays fully usable — document is unchanged, still PENDING_APPROVAL.
    document = await _get_document(client, legal_officer, document_id)
    assert document["status"] == "PENDING_APPROVAL"


async def test_changes_requested_loops_to_draft(client, db):
    from app.modules.users.models import Role

    fence_id = await _create_fence(db)
    uploader = await _create_user_and_login(
        client, db, email="uploader2@example.com", role=Role.AUTHORIZED_STAFF, fence_id=fence_id
    )
    reviewer = await _create_user_and_login(
        client, db, email="reviewer2@example.com", role=Role.REVIEWING_OFFICER, fence_id=fence_id
    )

    upload = await _upload(client, uploader)
    document_id = upload["document_id"]
    await _submit(client, uploader, document_id)

    # Missing comment on changes_requested -> rejected.
    resp = await client.post(
        f"/api/v1/documents/{document_id}/review",
        headers=_auth(reviewer),
        json={"decision": "changes_requested"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_REQUIRED"

    resp = await client.post(
        f"/api/v1/documents/{document_id}/review",
        headers=_auth(reviewer),
        json={"decision": "changes_requested", "comment": "fix clause 4"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "DRAFT"

    document = await _get_document(client, uploader, document_id)
    assert document["status"] == "DRAFT"
    versions = await _get_versions(client, uploader, document_id)
    assert versions[0]["status"] == "DRAFT"


async def test_illegal_transition_rejected(client, db):
    from app.modules.users.models import Role

    fence_id = await _create_fence(db)
    uploader = await _create_user_and_login(
        client, db, email="uploader3@example.com", role=Role.AUTHORIZED_STAFF, fence_id=fence_id
    )
    approver = await _create_user_and_login(
        client, db, email="approver3@example.com", role=Role.LEGAL_OFFICER, fence_id=fence_id
    )

    upload = await _upload(client, uploader)
    document_id = upload["document_id"]
    assert upload["status"] == "DRAFT"

    # DRAFT can't jump straight to APPROVED/ACTIVE via approve().
    resp = await client.post(
        f"/api/v1/documents/{document_id}/approve", headers={**_auth(approver), **_geo()}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ILLEGAL_TRANSITION"


async def test_anchor_failure_keeps_document_approved_and_app_usable(client, db, monkeypatch):
    from app.modules.users.models import Role

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("simulated RPC outage")

    monkeypatch.setattr(chain, "anchor_hash", _boom)

    # Keep the retry loop's backoff near-zero so this test stays fast.
    from app.modules.documents import workflow

    class _FastSettings:
        ANCHOR_MAX_ATTEMPTS = 2
        ANCHOR_RETRY_BACKOFF_SEC = 0.01
        ANCHOR_CONFIRM_POLL_ATTEMPTS = 1
        ANCHOR_CONFIRM_POLL_INTERVAL_SEC = 0.01

    monkeypatch.setattr(workflow, "get_settings", lambda: _FastSettings())

    fence_id = await _create_fence(db)
    uploader = await _create_user_and_login(
        client, db, email="uploader4@example.com", role=Role.AUTHORIZED_STAFF, fence_id=fence_id
    )
    reviewer = await _create_user_and_login(
        client, db, email="reviewer4@example.com", role=Role.REVIEWING_OFFICER, fence_id=fence_id
    )
    approver = await _create_user_and_login(
        client, db, email="approver4@example.com", role=Role.LEGAL_OFFICER, fence_id=fence_id
    )

    upload = await _upload(client, uploader)
    document_id = upload["document_id"]
    await _submit(client, uploader, document_id)
    await _review_approve(client, reviewer, document_id)

    resp = await client.post(
        f"/api/v1/documents/{document_id}/approve", headers={**_auth(approver), **_geo()}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "APPROVED"
    assert body["anchor_status"] == "FAILED"

    # Document is left APPROVED (pending anchor) — not stuck, not errored.
    document = await _get_document(client, approver, document_id)
    assert document["status"] == "APPROVED"

    # The app as a whole stays fully usable.
    listing = await client.get("/api/v1/documents", headers=_auth(approver))
    assert listing.status_code == 200


async def test_amendment_creates_v2_and_supersedes_v1_without_mutating_it(
    client, db, local_chain  # noqa: F811
):
    uploader, reviewer, approver = await _setup_three_roles(client, db)

    upload = await _upload(client, uploader)
    document_id = upload["document_id"]
    await _submit(client, uploader, document_id)
    await _review_approve(client, reviewer, document_id)
    approve_resp = await client.post(
        f"/api/v1/documents/{document_id}/approve", headers={**_auth(approver), **_geo()}
    )
    assert approve_resp.json()["status"] == "ACTIVE"

    versions_before = await _get_versions(client, approver, document_id)
    assert len(versions_before) == 1
    v1_snapshot = dict(versions_before[0])

    amend_resp = await client.post(
        f"/api/v1/documents/{document_id}/amend",
        headers={**_auth(uploader), **_geo()},
        json={"reason": "typo in clause 2"},
    )
    assert amend_resp.status_code == 200, amend_resp.text
    assert amend_resp.json()["status"] == "AMENDMENT_REQUESTED"

    upload_v2 = await _upload(client, uploader, data=PDF_BYTES_V2, amend_of=document_id)
    assert upload_v2["status"] == "DRAFT"
    assert upload_v2["sha256"] == hashlib.sha256(PDF_BYTES_V2).hexdigest()
    assert upload_v2["sha256"] != v1_snapshot["sha256"]

    versions_mid = await _get_versions(client, approver, document_id)
    assert len(versions_mid) == 2
    v2 = next(v for v in versions_mid if v["version_no"] == 2)
    assert v2["prev_version_hash"] == v1_snapshot["sha256"]
    assert v2["status"] == "DRAFT"

    await _submit(client, uploader, document_id)
    await _review_approve(client, reviewer, document_id)
    approve_v2_resp = await client.post(
        f"/api/v1/documents/{document_id}/approve", headers={**_auth(approver), **_geo()}
    )
    assert approve_v2_resp.status_code == 200, approve_v2_resp.text
    assert approve_v2_resp.json()["status"] == "ACTIVE"

    versions_after = await _get_versions(client, approver, document_id)
    assert len(versions_after) == 2
    v1_after = next(v for v in versions_after if v["version_no"] == 1)
    v2_after = next(v for v in versions_after if v["version_no"] == 2)

    assert v1_after["status"] == "SUPERSEDED"
    assert v1_after["sha256"] == v1_snapshot["sha256"]
    assert v1_after["storage_key"] == v1_snapshot["storage_key"]

    assert v2_after["status"] == "ACTIVE"
    assert v2_after["anchored"] is True

    document = await _get_document(client, approver, document_id)
    assert document["status"] == "ACTIVE"
    assert document["current_version_id"] == v2_after["id"]
