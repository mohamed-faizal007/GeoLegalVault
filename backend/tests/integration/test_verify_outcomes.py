"""REL-04 / D-049: verification must tell "could not check" from "not anchored", flag and audit
what it cannot explain, and never hang on a dead RPC.

Every test has a hard timeout (a hang is a failure, not a stuck run). Chain settings are set
explicitly (`chain_env` / `local_chain`); nothing reads a `.env`. No transaction is sent here
except the local Hardhat anchor that `_activate_document` performs on the throwaway node.
"""

import json
import time

import pytest
from bson import ObjectId

from app.services import storage
from app.services.hashing import sha256_bytes
from tests.integration.anchor_helpers import hard_timeout
from tests.integration.chain_outage_helpers import (
    NO_CODE_ADDRESS,
    SECRET,
    blackhole,
    chain_env,  # noqa: F401 (fixture)
    dead_port_url,
)
from tests.integration.test_anchor import local_chain  # noqa: F401 (reused fixture)
from tests.integration.test_integrity_clear import (
    REASON,
    TAMPERED_BYTES,
    _admin,
    _audit,
    _clear,
    _flagged_document,
)
from tests.integration.test_verify import _activate_document
from tests.integration.test_workflow import (
    PDF_BYTES,
    _auth,
    _create_fence,
    _create_user_and_login,
    _get_document,
    _upload,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _verify(client, token: str, version_id: str):
    return client.post(f"/api/v1/verify/{version_id}", headers=_auth(token))


async def _actions(db, version_id: str) -> list[str]:
    rows = await db["audit_logs"].find({"target_id": ObjectId(version_id)}).to_list(None)
    return [r["action"] for r in rows if r["action"].startswith("VERIFY")]


async def _records(db, version_id: str) -> list[dict]:
    return (
        await db["verification_records"]
        .find({"version_id": ObjectId(version_id)})
        .sort("created_at", 1)
        .to_list(None)
    )


async def _everything(db, version_id: str, document_id: str, *extra) -> str:
    audit = await db["audit_logs"].find({}).to_list(None)
    records = await _records(db, version_id)
    document = await db["documents"].find_one({"_id": ObjectId(document_id)})
    return json.dumps([audit, records, document, *extra], default=str)


async def _set_version(db, version_id: str, **fields) -> None:
    await db["document_versions"].update_one({"_id": ObjectId(version_id)}, {"$set": fields})


# --- chain unreachable / slow ------------------------------------------------------------


@hard_timeout(60)
async def test_unreachable_chain_is_reported_as_such_not_as_not_anchored(
    client, db, local_chain, chain_env, caplog  # noqa: F811
):
    approver, document_id, version_id, _key = await _activate_document(client, db)
    chain_env(SEPOLIA_RPC_URL=dead_port_url())

    resp = await _verify(client, approver, version_id)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["result"] == "CHAIN_UNREACHABLE"
    assert body["reason"] == "RPC_UNREACHABLE"
    assert body["onchain"] is None
    assert (await _get_document(client, approver, document_id))["integrity_flag"] is None
    actions = await _actions(db, version_id)
    assert "VERIFY_CHAIN_UNREACHABLE" in actions
    assert "VERIFY_NOT_ANCHORED" not in actions
    assert [r["result"] for r in await _records(db, version_id)] == ["CHAIN_UNREACHABLE"]
    assert SECRET not in await _everything(db, version_id, document_id, body)
    assert SECRET not in caplog.text


@hard_timeout(40)
async def test_a_stuck_chain_is_bounded_and_reported_as_a_timeout(
    client, db, local_chain, chain_env  # noqa: F811
):
    approver, _document_id, version_id, _key = await _activate_document(client, db)
    with blackhole() as stuck_url:
        chain_env(SEPOLIA_RPC_URL=stuck_url, CHAIN_READ_TIMEOUT_SEC=1)
        started = time.monotonic()
        resp = await _verify(client, approver, version_id)
        elapsed = time.monotonic() - started

    assert resp.status_code == 200, resp.text
    assert resp.json()["result"] == "CHAIN_UNREACHABLE"
    assert resp.json()["reason"] == "CHAIN_TIMEOUT"
    assert elapsed < 8, f"verify took {elapsed:.1f}s against a stuck node with a 1s read timeout"


@hard_timeout(90)
async def test_an_outage_between_two_good_runs_never_shows_not_anchored(
    client, db, local_chain, chain_env  # noqa: F811
):
    """The dev-data sequence: VERIFIED, (RPC dead), VERIFIED."""
    approver, document_id, version_id, _key = await _activate_document(client, db)
    import os

    good_url = os.environ["SEPOLIA_RPC_URL"]

    assert (await _verify(client, approver, version_id)).json()["result"] == "VERIFIED"
    chain_env(SEPOLIA_RPC_URL=dead_port_url())
    assert (await _verify(client, approver, version_id)).json()["result"] == "CHAIN_UNREACHABLE"
    chain_env(SEPOLIA_RPC_URL=good_url)
    assert (await _verify(client, approver, version_id)).json()["result"] == "VERIFIED"

    history = await client.get(f"/api/v1/verify/{version_id}/history", headers=_auth(approver))
    assert [i["result"] for i in reversed(history.json()["items"])] == [
        "VERIFIED",
        "CHAIN_UNREACHABLE",
        "VERIFIED",
    ]
    assert "VERIFY_NOT_ANCHORED" not in await _actions(db, version_id)
    assert (await _get_document(client, approver, document_id))["integrity_flag"] is None


@hard_timeout(60)
async def test_a_swapped_file_is_still_a_mismatch_while_the_chain_is_down(
    client, db, local_chain, chain_env  # noqa: F811
):
    approver, document_id, version_id, key = await _activate_document(client, db)
    storage.put_object(TAMPERED_BYTES, key, "application/pdf")
    chain_env(SEPOLIA_RPC_URL=dead_port_url())

    body = (await _verify(client, approver, version_id)).json()

    # The file no longer matches its recorded hash: provable without the chain.
    assert body["result"] == "MISMATCH"
    assert (await _get_document(client, approver, document_id))["integrity_flag"] == "TAMPERED"
    assert "VERIFY_FAIL" in await _actions(db, version_id)


# --- the chain answered "no" for a version the database says is anchored ------------------


@hard_timeout(60)
async def test_contract_with_no_code_is_anchor_missing_for_an_anchored_version(
    client, db, local_chain, chain_env  # noqa: F811
):
    approver, document_id, version_id, _key = await _activate_document(client, db)
    chain_env(CONTRACT_ADDRESS=NO_CODE_ADDRESS)  # a reset/redeployed chain: nothing at the address

    body = (await _verify(client, approver, version_id)).json()

    assert body["result"] == "ANCHOR_MISSING"
    assert body["reason"] == "CONTRACT_NOT_DEPLOYED"
    assert (await _get_document(client, approver, document_id))["integrity_flag"] == "UNCONFIRMED"
    assert "VERIFY_ANCHOR_MISSING" in await _actions(db, version_id)
    assert "VERIFY_NOT_ANCHORED" not in await _actions(db, version_id)


@hard_timeout(60)
async def test_contract_with_no_code_is_still_not_anchored_for_a_never_anchored_version(
    client, db, local_chain, chain_env  # noqa: F811
):
    fence_id = await _create_fence(db)
    from app.modules.users.models import Role

    uploader = await _create_user_and_login(
        client, db, email="draft-owner@example.com", role=Role.AUTHORIZED_STAFF, fence_id=fence_id
    )
    version_id = (await _upload(client, uploader))["version_id"]
    chain_env(CONTRACT_ADDRESS=NO_CODE_ADDRESS)

    body = (await _verify(client, uploader, version_id)).json()

    assert body["result"] == "NOT_ANCHORED"
    assert "VERIFY_ANCHOR_MISSING" not in await _actions(db, version_id)


@hard_timeout(60)
async def test_edited_version_no_on_an_anchored_version_is_flagged_not_grey(
    client, db, local_chain  # noqa: F811
):
    approver, document_id, version_id, _key = await _activate_document(client, db)
    await _set_version(db, version_id, version_no=99)

    body = (await _verify(client, approver, version_id)).json()

    assert body["result"] == "ANCHOR_MISSING"
    assert (await _get_document(client, approver, document_id))["integrity_flag"] == "UNCONFIRMED"
    assert "VERIFY_ANCHOR_MISSING" in await _actions(db, version_id)


@hard_timeout(60)
async def test_forged_bytes_forged_hash_and_edited_version_no_is_flagged(
    client, db, local_chain  # noqa: F811
):
    """The R13 case: bytes, sha256 and version_no all rewritten in the database/storage."""
    approver, document_id, version_id, key = await _activate_document(client, db)
    storage.put_object(TAMPERED_BYTES, key, "application/pdf")
    await _set_version(db, version_id, sha256=sha256_bytes(TAMPERED_BYTES), version_no=99)

    body = (await _verify(client, approver, version_id)).json()

    assert body["result"] == "ANCHOR_MISSING"
    assert body["recomputed"] == body["stored"]
    assert (await _get_document(client, approver, document_id))["integrity_flag"] == "UNCONFIRMED"
    assert "VERIFY_ANCHOR_MISSING" in await _actions(db, version_id)


@hard_timeout(60)
async def test_edited_version_no_on_a_never_anchored_version_stays_not_anchored(
    client, db, local_chain  # noqa: F811
):
    from app.modules.users.models import Role

    fence_id = await _create_fence(db)
    uploader = await _create_user_and_login(
        client, db, email="draft-owner2@example.com", role=Role.AUTHORIZED_STAFF, fence_id=fence_id
    )
    upload = await _upload(client, uploader)
    await _set_version(db, upload["version_id"], version_no=99)

    body = (await _verify(client, uploader, upload["version_id"])).json()

    assert body["result"] == "NOT_ANCHORED"
    document = await db["documents"].find_one({"_id": ObjectId(upload["document_id"])})
    assert document["integrity_flag"] is None


# --- storage ---------------------------------------------------------------------------


@hard_timeout(60)
async def test_a_missing_stored_file_is_file_missing_flagged_and_audited(
    client, db, local_chain  # noqa: F811
):
    approver, document_id, version_id, key = await _activate_document(client, db)
    storage.delete_object(key)

    resp = await _verify(client, approver, version_id)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["result"] == "FILE_MISSING"
    assert body["recomputed"] is None
    assert (await _get_document(client, approver, document_id))["integrity_flag"] == "UNCONFIRMED"
    assert "VERIFY_FILE_MISSING" in await _actions(db, version_id)
    history = await client.get(f"/api/v1/verify/{version_id}/history", headers=_auth(approver))
    assert history.status_code == 200, history.text
    assert history.json()["items"][0]["result"] == "FILE_MISSING"


@hard_timeout(60)
async def test_a_storage_outage_is_a_503_that_is_audited_and_does_not_flag(
    client, db, local_chain, monkeypatch  # noqa: F811
):
    approver, document_id, version_id, _key = await _activate_document(client, db)

    def _down(_key):
        raise OSError("storage down")

    monkeypatch.setattr(storage, "get_object", _down)
    resp = await _verify(client, approver, version_id)

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "STORAGE_UNAVAILABLE"
    assert "VERIFY_STORAGE_UNAVAILABLE" in await _actions(db, version_id)
    assert await _records(db, version_id) == []
    assert (await _get_document(client, approver, document_id))["integrity_flag"] is None


# --- D-025 clearing never treats "could not check" as verified ---------------------------


@hard_timeout(90)
async def test_clearing_is_refused_while_the_chain_is_unreachable(
    client, db, local_chain, chain_env  # noqa: F811
):
    _approver, admin, document_id, _vid, key = await _flagged_document(client, db)
    storage.put_object(PDF_BYTES, key, "application/pdf")  # the bytes are fine again
    chain_env(SEPOLIA_RPC_URL=dead_port_url())

    resp = await _clear(client, admin, document_id)

    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == "INTEGRITY_STILL_FAILING"
    assert "CHAIN_UNREACHABLE" in resp.json()["error"]["message"]
    assert "unable to verify" in resp.json()["error"]["message"]
    assert SECRET not in resp.text
    document = await db["documents"].find_one({"_id": ObjectId(document_id)})
    assert document["integrity_flag"] == "TAMPERED"
    assert await _audit(db, document_id, "INTEGRITY_CLEARED") == []
    (refused,) = await _audit(db, document_id, "INTEGRITY_CLEAR_REFUSED")
    assert refused["meta"]["failing"] == [{"version_no": 1, "result": "CHAIN_UNREACHABLE"}]


@hard_timeout(90)
async def test_an_unconfirmed_flag_clears_only_once_the_version_really_verifies(
    client, db, local_chain  # noqa: F811
):
    approver, document_id, version_id, _key = await _activate_document(client, db)
    await _set_version(db, version_id, version_no=99)
    assert (await _verify(client, approver, version_id)).json()["result"] == "ANCHOR_MISSING"
    admin = await _admin(client, db)

    refused = await _clear(client, admin, document_id)
    assert refused.status_code == 409, refused.text
    assert "ANCHOR_MISSING" in refused.json()["error"]["message"]
    document = await db["documents"].find_one({"_id": ObjectId(document_id)})
    assert document["integrity_flag"] == "UNCONFIRMED"

    await _set_version(db, version_id, version_no=1)  # the real key again
    cleared = await _clear(client, admin, document_id)

    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["integrity_flag"] is None
    (row,) = await _audit(db, document_id, "INTEGRITY_CLEARED")
    assert row["meta"]["reason"] == REASON


@hard_timeout(60)
async def test_an_unconfirmed_flag_never_downgrades_tampered(
    client, db, local_chain  # noqa: F811
):
    approver, document_id, version_id, key = await _activate_document(client, db)
    storage.put_object(TAMPERED_BYTES, key, "application/pdf")
    assert (await _verify(client, approver, version_id)).json()["result"] == "MISMATCH"
    storage.delete_object(key)

    assert (await _verify(client, approver, version_id)).json()["result"] == "FILE_MISSING"

    document = await db["documents"].find_one({"_id": ObjectId(document_id)})
    assert document["integrity_flag"] == "TAMPERED"
