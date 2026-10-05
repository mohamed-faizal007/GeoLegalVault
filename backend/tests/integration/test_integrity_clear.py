"""D-025: clearing a TAMPERED flag is admin-only, needs a written reason, is
audited, and re-runs the real 3-way verification first — it must refuse
whenever any anchored version does not verify, so it can never be used to
hide a real mismatch."""

import pytest
from bson import ObjectId

from app.modules.documents import service as documents_service
from app.modules.users.models import Role
from app.modules.verify import service as verify_service
from app.services import blockchain as chain
from app.services import storage
from tests.integration.test_anchor import local_chain  # noqa: F401 (reused fixture)
from tests.integration.test_concurrency import (
    _active_document_with_amendment_requested,
    _fence_id,
)
from tests.integration.test_verify import _activate_document
from tests.integration.test_workflow import (
    PDF_BYTES,
    _auth,
    _create_user_and_login,
    _geo,
    _get_document,
    _get_versions,
    _review_approve,
    _submit,
    _upload,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")

REASON = "Original file restored from the nightly backup after the storage incident."
TAMPERED_BYTES = PDF_BYTES[:-1] + bytes([PDF_BYTES[-1] ^ 0xFF])


async def _admin(client, db) -> str:
    return await _create_user_and_login(
        client,
        db,
        email="integrity-admin@example.com",
        role=Role.ADMINISTRATOR,
        fence_id=await _fence_id(db),
    )


def _clear(client, token: str, document_id: str, reason=REASON):
    return client.post(
        f"/api/v1/documents/{document_id}/integrity/clear",
        headers=_auth(token),
        json={"reason": reason} if reason is not None else {},
    )


async def _flagged_document(client, db):
    """ACTIVE+anchored document whose stored object was swapped, then verified
    -> MISMATCH -> flagged TAMPERED. Returns (approver, admin, doc_id, ver_id, key)."""
    approver, document_id, version_id, key = await _activate_document(client, db)
    storage.put_object(TAMPERED_BYTES, key, "application/pdf")
    verdict = await client.post(f"/api/v1/verify/{version_id}", headers=_auth(approver))
    assert verdict.json()["result"] == "MISMATCH"
    assert (await _get_document(client, approver, document_id))["integrity_flag"] == "TAMPERED"
    return approver, await _admin(client, db), document_id, version_id, key


async def _audit(db, document_id: str, action: str) -> list[dict]:
    return await db["audit_logs"].find(
        {"target_id": ObjectId(document_id), "action": action}
    ).to_list(None)


async def test_clear_refuses_while_the_stored_bytes_are_still_wrong(
    client, db, local_chain  # noqa: F811
):
    approver, admin, document_id, _vid, _key = await _flagged_document(client, db)

    resp = await _clear(client, admin, document_id)

    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == "INTEGRITY_STILL_FAILING"
    assert "MISMATCH" in resp.json()["error"]["message"]
    assert (await _get_document(client, approver, document_id))["integrity_flag"] == "TAMPERED"
    refused = await _audit(db, document_id, "INTEGRITY_CLEAR_REFUSED")
    assert len(refused) == 1 and refused[0]["meta"]["reason"] == REASON
    assert await _audit(db, document_id, "INTEGRITY_CLEARED") == []


async def test_clear_succeeds_after_the_original_bytes_are_restored_and_is_audited(
    client, db, local_chain  # noqa: F811
):
    approver, admin, document_id, version_id, key = await _flagged_document(client, db)
    storage.put_object(PDF_BYTES, key, "application/pdf")  # operator restores the original

    resp = await _clear(client, admin, document_id)

    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "document_id": document_id,
        "integrity_flag": None,
        "verified_versions": [1],
    }
    assert (await _get_document(client, approver, document_id))["integrity_flag"] is None

    cleared = await _audit(db, document_id, "INTEGRITY_CLEARED")
    assert len(cleared) == 1
    assert cleared[0]["meta"] == {"reason": REASON, "verified_versions": [1]}
    document = await db["documents"].find_one({"_id": ObjectId(document_id)})
    assert document["integrity_cleared"]["reason"] == REASON
    assert document["integrity_cleared"]["by"] == cleared[0]["actor_id"]
    # The re-verification really ran: a MISMATCH record, then a VERIFIED one.
    results = [
        r["result"]
        for r in await db["verification_records"]
        .find({"version_id": ObjectId(version_id)})
        .sort("created_at", 1)
        .to_list(None)
    ]
    assert results == ["MISMATCH", "VERIFIED"]


async def test_clear_on_an_unflagged_document_is_a_409(client, db, local_chain):  # noqa: F811
    _approver, document_id, _vid, _key = await _activate_document(client, db)
    admin = await _admin(client, db)

    resp = await _clear(client, admin, document_id)

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "NOT_FLAGGED"
    assert await _audit(db, document_id, "INTEGRITY_CLEARED") == []


@pytest.mark.parametrize("reason", [None, "", "short", "          ", "x" * 1001])
async def test_clear_requires_a_real_written_reason(
    client, db, local_chain, reason  # noqa: F811
):
    _approver, admin, document_id, _vid, key = await _flagged_document(client, db)
    storage.put_object(PDF_BYTES, key, "application/pdf")

    resp = await _clear(client, admin, document_id, reason=reason)

    assert resp.status_code == 422, resp.text
    assert await _audit(db, document_id, "INTEGRITY_CLEARED") == []
    doc = await db["documents"].find_one({"_id": ObjectId(document_id)})
    assert doc["integrity_flag"] == "TAMPERED"


async def test_only_administrators_may_clear_the_flag(client, db, local_chain):  # noqa: F811
    approver, _admin_token, document_id, _vid, key = await _flagged_document(client, db)
    storage.put_object(PDF_BYTES, key, "application/pdf")  # would verify fine
    fence = await _fence_id(db)
    others = {
        "legal officer": approver,
        "staff": await _create_user_and_login(
            client, db, email="s@example.com", role=Role.AUTHORIZED_STAFF, fence_id=fence
        ),
        "reviewer": await _create_user_and_login(
            client, db, email="r@example.com", role=Role.REVIEWING_OFFICER, fence_id=fence
        ),
        "auditor": await _create_user_and_login(
            client, db, email="a@example.com", role=Role.AUDITOR, fence_id=fence
        ),
    }
    for name, token in others.items():
        resp = await _clear(client, token, document_id)
        assert resp.status_code == 403, (name, resp.text)
    unauth = await client.post(
        f"/api/v1/documents/{document_id}/integrity/clear", json={"reason": REASON}
    )
    assert unauth.status_code == 401
    doc = await db["documents"].find_one({"_id": ObjectId(document_id)})
    assert doc["integrity_flag"] == "TAMPERED"


async def test_clear_refuses_when_the_chain_cannot_be_read(
    client, db, local_chain, monkeypatch  # noqa: F811
):
    _approver, admin, document_id, _vid, key = await _flagged_document(client, db)
    storage.put_object(PDF_BYTES, key, "application/pdf")  # bytes are fine now

    async def _down(*_a, **_k):
        raise ConnectionError("rpc down")

    monkeypatch.setattr(chain, "get_onchain_anchor", _down)
    resp = await _clear(client, admin, document_id)

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INTEGRITY_STILL_FAILING"
    # Unable to reach the chain is "could not verify", not "not anchored" (D-049).
    assert "CHAIN_UNREACHABLE" in resp.json()["error"]["message"]
    doc = await db["documents"].find_one({"_id": ObjectId(document_id)})
    assert doc["integrity_flag"] == "TAMPERED"


async def test_clear_refuses_when_storage_cannot_be_read(
    client, db, local_chain, monkeypatch  # noqa: F811
):
    _approver, admin, document_id, _vid, _key = await _flagged_document(client, db)

    def _down(_key):
        raise OSError("storage down")

    monkeypatch.setattr(storage, "get_object", _down)
    resp = await _clear(client, admin, document_id)

    assert resp.status_code == 409
    assert "UNVERIFIABLE" in resp.json()["error"]["message"]
    doc = await db["documents"].find_one({"_id": ObjectId(document_id)})
    assert doc["integrity_flag"] == "TAMPERED"


async def test_clear_is_refused_if_the_document_changes_while_it_is_being_verified(
    client, db, local_chain, monkeypatch  # noqa: F811
):
    _approver, admin, document_id, _vid, key = await _flagged_document(client, db)
    storage.put_object(PDF_BYTES, key, "application/pdf")
    real_verify = verify_service.verify_version

    async def _verify_then_concurrent_write(db_, *, version_id, actor):
        result = await real_verify(db_, version_id=version_id, actor=actor)
        # Another request records a mismatch / touches the document mid-verification.
        await documents_service.set_integrity_flag(db_, ObjectId(document_id), "TAMPERED")
        return result

    monkeypatch.setattr(verify_service, "verify_version", _verify_then_concurrent_write)
    resp = await _clear(client, admin, document_id)

    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == "ILLEGAL_TRANSITION"
    doc = await db["documents"].find_one({"_id": ObjectId(document_id)})
    assert doc["integrity_flag"] == "TAMPERED"
    assert await _audit(db, document_id, "INTEGRITY_CLEARED") == []


async def test_a_mismatch_on_any_anchored_version_blocks_clearing(
    client, db, local_chain  # noqa: F811
):
    """V1 (now SUPERSEDED) is tampered while V2 is clean: clearing must verify
    *every* anchored version, not just the live one."""
    ctx = await _active_document_with_amendment_requested(client, db)
    document_id = ctx["document_id"]
    v2_bytes = PDF_BYTES + b"-corrected"
    amend = await _upload(client, ctx["uploader"], data=v2_bytes, amend_of=document_id)
    assert amend["status"] == "DRAFT"
    await _submit(client, ctx["uploader"], document_id)
    await _review_approve(client, ctx["reviewer"], document_id)
    approved = await client.post(
        f"/api/v1/documents/{document_id}/approve", headers={**_auth(ctx["approver"]), **_geo()}
    )
    assert approved.json()["status"] == "ACTIVE", approved.text
    v1, v2 = await _get_versions(client, ctx["approver"], document_id)

    storage.put_object(TAMPERED_BYTES, v1["storage_key"], "application/pdf")
    verdict = await client.post(f"/api/v1/verify/{v1['id']}", headers=_auth(ctx["approver"]))
    assert verdict.json()["result"] == "MISMATCH"
    admin = await _admin(client, db)

    refused = await _clear(client, admin, document_id)
    assert refused.status_code == 409
    assert "v1: MISMATCH" in refused.json()["error"]["message"]
    assert "v2" not in refused.json()["error"]["message"]

    storage.put_object(PDF_BYTES, v1["storage_key"], "application/pdf")
    ok = await _clear(client, admin, document_id)
    assert ok.status_code == 200, ok.text
    assert ok.json()["verified_versions"] == [1, 2]
