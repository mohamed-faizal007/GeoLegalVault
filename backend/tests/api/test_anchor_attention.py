"""GET /blockchain/anchors/attention and POST /blockchain/anchors/{id}/retry (D-041).

No chain is needed: stuck documents are produced by approving while every send fails.
The retry endpoint only re-queues; these tests also prove it never signs or sends.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

from app.core.rbac import has_permission
from app.modules.users.models import Role
from app.services import blockchain as chain
from tests.integration.anchor_helpers import (
    FAKE_SECRET,
    LEAKY_RPC_ERROR,
    anchor_rows,
    everything_as_text,
    fast_anchor,  # noqa: F401 (fixture)
    hard_timeout,
    naive,
    run_pass,
)
from tests.integration.test_concurrency import _pending_approval
from tests.integration.test_workflow import _auth, _create_user_and_login, _geo

pytestmark = pytest.mark.asyncio(loop_scope="session")

ATTENTION = "/api/v1/blockchain/anchors/attention"
REASON = "Wallet funded again, re-driving the anchor"
ITEM_KEYS = {
    "document_id",
    "title",
    "title_hidden",  # D-052: a flag, not data about the document
    "version_no",
    "state",
    "last_error",
    "attempts",
    "next_attempt_at",
    "stuck_since",
    "can_retry",
}


def _retry_url(document_id: str) -> str:
    return f"/api/v1/blockchain/anchors/{document_id}/retry"


async def _stuck(client, db, error: Exception | None = None) -> dict:
    """A document left APPROVED because every send failed. Also returns tokens."""
    ctx = await _pending_approval(client, db)
    failing = AsyncMock(side_effect=error or ConnectionError(LEAKY_RPC_ERROR))
    with patch.object(chain, "anchor_hash", new=failing):
        response = await client.post(
            f"/api/v1/documents/{ctx['document_id']}/approve",
            headers={**_auth(ctx["approvers"][0]), **_geo()},
        )
    assert response.status_code == 200, response.text
    ctx["admin"] = await _create_user_and_login(
        client, db, email="admin@example.com", role=Role.ADMINISTRATOR, fence_id=ctx["fence"]
    )
    ctx["auditor"] = await _create_user_and_login(
        client, db, email="auditor@example.com", role=Role.AUDITOR, fence_id=ctx["fence"]
    )
    return ctx


async def _attention(client, token: str):
    return await client.get(ATTENTION, headers=_auth(token))


async def _retry(client, token: str, document_id: str, *, headers=None, json=None):
    return await client.post(
        _retry_url(document_id),
        headers=headers if headers is not None else {**_auth(token), **_geo()},
        json=json if json is not None else {"reason": REASON},
    )


async def _doc(db, ctx) -> dict:
    return await db["documents"].find_one({"_id": ObjectId(ctx["document_id"])})


# --- the permission map ----------------------------------------------------------


async def test_permission_map_view_for_admin_legal_auditor_retry_for_admin_only():
    viewers = {Role.ADMINISTRATOR, Role.LEGAL_OFFICER, Role.AUDITOR}
    for role in Role:
        assert has_permission(role.value, "anchor:view") is (role in viewers), role
        assert has_permission(role.value, "anchor:retry") is (role is Role.ADMINISTRATOR), role


# --- GET /attention ---------------------------------------------------------------


@hard_timeout(120)
async def test_attention_is_visible_to_admin_legal_officer_auditor_only(client, db, fast_anchor):  # noqa: F811
    ctx = await _stuck(client, db)
    allowed = {"admin": ctx["admin"], "legal": ctx["approvers"][0], "auditor": ctx["auditor"]}
    denied = {"reviewer": ctx["reviewer"], "uploader": ctx["uploader"]}

    for name, token in allowed.items():
        response = await _attention(client, token)
        assert response.status_code == 200, (name, response.text)
        assert response.json()["total"] == 1
    for name, token in denied.items():
        response = await _attention(client, token)
        assert response.status_code == 403, name
        assert response.json()["error"]["code"] == "FORBIDDEN"
    assert (await client.get(ATTENTION)).status_code == 401


@hard_timeout(120)
async def test_attention_item_shape_state_and_no_secrets(client, db, fast_anchor):  # noqa: F811
    ctx = await _stuck(client, db)
    response = await _attention(client, ctx["auditor"])
    (item,) = response.json()["items"]

    assert set(item) == ITEM_KEYS
    assert item["document_id"] == ctx["document_id"] and item["version_no"] == 1
    assert item["state"] == "RETRYING" and item["last_error"] == "RPC_UNREACHABLE"
    assert item["attempts"] == 0 and item["next_attempt_at"] is not None
    assert item["can_retry"] is False  # an auditor may look, not act

    admin_item = (await _attention(client, ctx["admin"])).json()["items"][0]
    assert admin_item["can_retry"] is True

    text = response.text
    assert FAKE_SECRET not in text and "alchemy" not in text
    for forbidden in ("sha256", "storage_key", "tx_hash", "contract_address", "SEPOLIA"):
        assert forbidden not in text


@hard_timeout(120)
async def test_permanent_failure_is_reported_with_its_code(client, db, fast_anchor):  # noqa: F811
    not_configured = chain.BlockchainNotConfigured("SEPOLIA_RPC_URL is not configured")
    ctx = await _stuck(client, db, error=not_configured)
    (item,) = (await _attention(client, ctx["admin"])).json()["items"]
    assert item["state"] == "PERMANENT_FAILURE" and item["last_error"] == "NOT_CONFIGURED"
    assert (await _doc(db, ctx))["anchor_retry"]["permanent"] is True


@hard_timeout(120)
async def test_a_legacy_stuck_document_reads_as_needs_admin_retry_and_get_writes_nothing(
    client, db, fast_anchor  # noqa: F811
):
    """The shape of the dev DB's 'Approval Demo': APPROVED, FAILED rows with raw pre-D-020
    error text, no `live` field, no anchor_retry, 36 days old."""
    ctx = await _stuck(client, db)
    old = datetime.now(UTC) - timedelta(days=36)
    document_id = ObjectId(ctx["document_id"])
    await db["documents"].update_one(
        {"_id": document_id}, {"$unset": {"anchor_retry": ""}, "$set": {"updated_at": old}}
    )
    await db["blockchain_anchors"].update_many(
        {"document_id": document_id},
        {
            "$set": {"created_at": old, "error": "SEPOLIA_RPC_URL is not configured"},
            "$unset": {"live": ""},
        },
    )
    before = await _doc(db, ctx)

    (item,) = (await _attention(client, ctx["admin"])).json()["items"]
    assert item["state"] == "NEEDS_ADMIN_RETRY"
    assert item["last_error"] == "ANCHOR_FAILED"  # raw legacy text collapses, never echoed
    assert "SEPOLIA_RPC_URL" not in str(item)
    assert await _doc(db, ctx) == before, "a GET must not write"


@hard_timeout(120)
async def test_documents_that_are_not_approved_are_not_listed(client, db, fast_anchor):  # noqa: F811
    ctx = await _pending_approval(client, db)  # PENDING_APPROVAL, never approved
    admin = await _create_user_and_login(
        client, db, email="admin@example.com", role=Role.ADMINISTRATOR, fence_id=ctx["fence"]
    )
    body = (await _attention(client, admin)).json()
    assert body["items"] == [] and body["total"] == 0


# --- POST /retry ------------------------------------------------------------------


@hard_timeout(120)
async def test_admin_retry_requeues_only_and_never_signs_or_sends(client, db, fast_anchor):  # noqa: F811
    ctx = await _stuck(client, db, error=chain.BlockchainNotConfigured("not configured"))
    assert (await _doc(db, ctx))["anchor_retry"]["permanent"] is True
    started = naive(datetime.now(UTC))

    spy = AsyncMock(wraps=chain.anchor_hash)
    with patch.object(chain, "anchor_hash", new=spy), patch.object(
        chain, "get_service_account", side_effect=AssertionError("the API must never sign")
    ):
        response = await _retry(client, ctx["admin"], ctx["document_id"])
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "RETRYING"
    assert spy.await_count == 0

    retry = (await _doc(db, ctx))["anchor_retry"]
    assert retry["permanent"] is False and retry["attempts"] == 0
    assert retry.get("permanent_reason") is None
    assert naive(retry["queued_at"]) >= started and naive(retry["next_attempt_at"]) >= started
    admin_user = await db["users"].find_one({"email": "admin@example.com"})
    assert str(retry["requeued_by"]) == str(admin_user["_id"])

    (audit,) = await db["audit_logs"].find({"action": "ANCHOR_RETRY_REQUESTED"}).to_list(None)
    assert audit["meta"]["reason"] == REASON
    assert audit["result"] == "SUCCESS" and str(audit["target_id"]) == ctx["document_id"]
    assert (await _doc(db, ctx))["status"] == "APPROVED"


@hard_timeout(120)
@pytest.mark.parametrize("role_key", ["legal", "auditor", "reviewer", "uploader"])
async def test_retry_is_forbidden_for_every_role_but_admin_and_is_rbac_before_geofence(
    client, db, fast_anchor, role_key  # noqa: F811
):
    ctx = await _stuck(client, db)
    token = {
        "legal": ctx["approvers"][0],
        "auditor": ctx["auditor"],
        "reviewer": ctx["reviewer"],
        "uploader": ctx["uploader"],
    }[role_key]
    outside = _geo(**{"X-Geo-Lat": "40.7", "X-Geo-Lng": "-74.0"})

    response = await _retry(client, token, ctx["document_id"], headers={**_auth(token), **outside})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"  # not a location code: RBAC ran first


@hard_timeout(120)
async def test_retry_needs_a_location_inside_the_admins_geofence(client, db, fast_anchor):  # noqa: F811
    ctx = await _stuck(client, db)
    before = await _doc(db, ctx)

    outside = {**_auth(ctx["admin"]), **_geo(**{"X-Geo-Lat": "40.7", "X-Geo-Lng": "-74.0"})}
    refused = await _retry(client, ctx["admin"], ctx["document_id"], headers=outside)
    assert refused.status_code == 403
    no_location = _auth(ctx["admin"])
    # same as approve/upload: a missing location is an InvalidLocation (422), not a denial
    refused = await _retry(client, ctx["admin"], ctx["document_id"], headers=no_location)
    assert refused.status_code == 422
    assert await _doc(db, ctx) == before
    assert (await db["audit_logs"].count_documents({"action": "ANCHOR_RETRY_REQUESTED"})) == 0


@hard_timeout(120)
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"reason": "too short"},
        {"reason": "x" * 1001},
        {"reason": REASON, "sha256": "aa" * 32},  # nothing in the request may name a hash
        {"reason": REASON, "version_no": 2},
        {"reason": REASON, "tx_hash": "0x" + "11" * 32},
    ],
)
async def test_retry_body_is_strict(client, db, fast_anchor, body):  # noqa: F811
    ctx = await _stuck(client, db)
    response = await _retry(client, ctx["admin"], ctx["document_id"], json=body)
    assert response.status_code == 422


@hard_timeout(120)
async def test_retry_rejects_unknown_documents_and_documents_that_are_not_approved(
    client, db, fast_anchor  # noqa: F811
):
    ctx = await _pending_approval(client, db)  # PENDING_APPROVAL
    admin = await _create_user_and_login(
        client, db, email="admin@example.com", role=Role.ADMINISTRATOR, fence_id=ctx["fence"]
    )
    assert (await _retry(client, admin, ctx["document_id"])).status_code == 409
    assert (await _retry(client, admin, str(ObjectId()))).status_code == 404
    assert (await _retry(client, admin, "not-an-object-id")).status_code == 404


@hard_timeout(120)
async def test_retry_refuses_while_leased_or_while_an_anchor_is_in_flight(client, db, fast_anchor):  # noqa: F811
    ctx = await _stuck(client, db)
    document_id = ObjectId(ctx["document_id"])
    lease = naive(datetime.now(UTC)) + timedelta(seconds=30)
    await db["documents"].update_one(
        {"_id": document_id},
        {"$set": {"anchor_retry.lease_owner": "worker-1", "anchor_retry.lease_until": lease}},
    )
    assert (await _retry(client, ctx["admin"], ctx["document_id"])).status_code == 409

    await db["documents"].update_one(
        {"_id": document_id}, {"$unset": {"anchor_retry.lease_until": ""}}
    )
    (row,) = await anchor_rows(db, ctx["document_id"])
    in_flight = {k: v for k, v in row.items() if k != "_id"}
    in_flight.update(status="PENDING", tx_hash="0x" + "ab" * 32)
    await db["blockchain_anchors"].insert_one(in_flight)
    assert (await _retry(client, ctx["admin"], ctx["document_id"])).status_code == 409


# --- the age cutoff: old stuck rows are never auto-sent (D-040) ----------------------


@hard_timeout(120)
async def test_old_stuck_documents_are_not_auto_sent_until_an_admin_requeues(
    client, db, fast_anchor  # noqa: F811
):
    ctx = await _stuck(client, db)
    old = datetime.now(UTC) - timedelta(days=8)
    await db["documents"].update_one(
        {"_id": ObjectId(ctx["document_id"])},
        {"$set": {"anchor_retry.queued_at": old, "anchor_retry.next_attempt_at": old}},
    )

    spy = AsyncMock(side_effect=ConnectionError(LEAKY_RPC_ERROR))
    # The worker reads the chain ("is it already anchored?") before it sends. Fake that read too,
    # so the test needs no chain settings and no network (D-047).
    not_anchored = AsyncMock(return_value={"exists": False})
    with (
        patch.object(chain, "anchor_hash", new=spy),
        patch.object(chain, "get_onchain_anchor", new=not_anchored),
    ):
        for _ in range(3):
            await run_pass(db)
        assert spy.await_count == 0, "the worker sent for a document older than the cutoff"
        (item,) = (await _attention(client, ctx["admin"])).json()["items"]
        assert item["state"] == "NEEDS_ADMIN_RETRY"

        assert (await _retry(client, ctx["admin"], ctx["document_id"])).status_code == 200
        await run_pass(db)
        assert spy.await_count == 1, "after an admin re-queue the worker should act"
    assert FAKE_SECRET not in everything_as_text(await _doc(db, ctx))
