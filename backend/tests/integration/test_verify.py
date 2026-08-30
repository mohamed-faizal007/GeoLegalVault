"""Integration tests for the 3-way verification loop (Plan Part 6 Scenario 5,
Phase 7): recompute SHA-256 from the stored bytes and compare against (a)
the hash recorded at upload time and (b) the hash read live from the
Sepolia (here: local Hardhat) contract.

Reuses the local Hardhat node fixture and the upload/submit/review/approve
helpers already built for the lifecycle workflow tests (test_workflow.py) to
drive a document to ACTIVE + BLOCKCHAIN_ANCHORED before verifying it.
"""

import pytest
from bson import ObjectId

from app.services import storage
from app.services.hashing import sha256_bytes
from tests.integration.test_anchor import local_chain  # noqa: F401 (reused fixture)
from tests.integration.test_workflow import (  # noqa: F401 (reused helpers)
    PDF_BYTES,
    _auth,
    _create_fence,
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


async def _approve(client, token: str, document_id: str) -> dict:
    resp = await client.post(
        f"/api/v1/documents/{document_id}/approve", headers={**_auth(token), **_geo()}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _activate_document(client, db) -> tuple[str, str, str, str]:
    """Runs a fresh document all the way to ACTIVE + CONFIRMED anchor.
    Returns (approver_token, document_id, version_id, storage_key)."""
    uploader, reviewer, approver = await _setup_three_roles(client, db)

    upload = await _upload(client, uploader)
    document_id = upload["document_id"]
    version_id = upload["version_id"]

    await _submit(client, uploader, document_id)
    await _review_approve(client, reviewer, document_id)
    approved = await _approve(client, approver, document_id)
    assert approved["status"] == "ACTIVE"
    assert approved["anchor_status"] == "CONFIRMED"

    versions = await _get_versions(client, approver, document_id)
    storage_key = versions[0]["storage_key"]
    return approver, document_id, version_id, storage_key


async def test_verify_untouched_anchored_version_is_verified(client, db, local_chain):  # noqa: F811
    approver, _document_id, version_id, _storage_key = await _activate_document(client, db)

    resp = await client.post(f"/api/v1/verify/{version_id}", headers=_auth(approver))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["result"] == "VERIFIED"
    assert body["recomputed"] == body["stored"] == body["onchain"]
    assert body["tx_hash"] is not None and body["tx_hash"].startswith("0x")
    assert body["etherscan_url"] == f"https://sepolia.etherscan.io/tx/{body['tx_hash']}"

    history = await client.get(f"/api/v1/verify/{version_id}/history", headers=_auth(approver))
    assert history.status_code == 200, history.text
    items = history.json()["items"]
    assert len(items) == 1
    assert items[0]["result"] == "VERIFIED"


async def test_verify_detects_tampered_blob(client, db, local_chain):  # noqa: F811
    approver, document_id, version_id, storage_key = await _activate_document(client, db)

    tampered = PDF_BYTES[:-1] + bytes([PDF_BYTES[-1] ^ 0xFF])
    storage.put_object(tampered, storage_key, "application/pdf")

    resp = await client.post(f"/api/v1/verify/{version_id}", headers=_auth(approver))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["result"] == "MISMATCH"
    assert body["recomputed"] != body["stored"]
    assert body["recomputed"] != body["onchain"]

    document = await _get_document(client, approver, document_id)
    assert document["integrity_flag"] == "TAMPERED"


async def test_verify_tampered_stored_hash_still_mismatches_onchain(client, db, local_chain):  # noqa: F811
    """Even if an attacker rewrites document_versions.sha256 directly in
    Mongo to match a tampered file, the immutable on-chain hash still
    disagrees — this is the entire point of anchoring (Plan Part 6:
    'Attacker edits MongoDB metadata to change the stored hash... on-chain
    hash is immutable -> Verify still MISMATCH')."""
    approver, document_id, version_id, storage_key = await _activate_document(client, db)

    tampered = PDF_BYTES[:-1] + bytes([PDF_BYTES[-1] ^ 0xFF])
    storage.put_object(tampered, storage_key, "application/pdf")
    fake_hash = sha256_bytes(tampered)
    await db["document_versions"].update_one(
        {"_id": ObjectId(version_id)}, {"$set": {"sha256": fake_hash}}
    )

    resp = await client.post(f"/api/v1/verify/{version_id}", headers=_auth(approver))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["result"] == "MISMATCH"
    assert body["recomputed"] == body["stored"]  # DB was tampered to match
    assert body["recomputed"] != body["onchain"]  # but the chain still disagrees

    document = await _get_document(client, approver, document_id)
    assert document["integrity_flag"] == "TAMPERED"


async def test_verify_never_anchored_version_is_not_anchored(client, db):
    from app.modules.users.models import Role

    fence_id = await _create_fence(db)
    uploader = await _create_user_and_login(
        client,
        db,
        email="never-anchored@example.com",
        role=Role.AUTHORIZED_STAFF,
        fence_id=fence_id,
    )

    upload = await _upload(client, uploader)
    version_id = upload["version_id"]

    resp = await client.post(f"/api/v1/verify/{version_id}", headers=_auth(uploader))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["result"] == "NOT_ANCHORED"
    assert body["onchain"] is None
    assert body["recomputed"] == body["stored"]
    assert body["tx_hash"] is None
    assert body["etherscan_url"] is None


async def test_verify_unknown_version_returns_404(client, db):
    from app.modules.users.models import Role

    fence_id = await _create_fence(db)
    viewer = await _create_user_and_login(
        client, db, email="viewer-verify@example.com", role=Role.AUDITOR, fence_id=fence_id
    )

    resp = await client.post(f"/api/v1/verify/{ObjectId()}", headers=_auth(viewer))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"
