"""D-054..D-057: readable names instead of ids, audit filters, login attempt count, explorer link.

Everything runs against the throwaway `geolegalvault_test` database (see conftest); no dev data,
no network, no transaction.
"""

import pytest

from app.core.config import get_settings
from app.modules.blockchain import service as blockchain_service
from app.modules.users.models import Role
from tests.integration.test_classification_access import (
    LOW_USERS,
    SECRET_TITLE,
    _world,
)
from tests.integration.test_workflow import PASSWORD, _auth, _create_user_and_login

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _name_users(db) -> None:
    users = db["users"]
    await users.update_one({"email": "owner@example.com"}, {"$set": {"name": "Olivia Owner"}})
    await users.update_one({"email": "auditor@example.com"}, {"$set": {"name": "Ada Auditor"}})


# --- A: names instead of ids -------------------------------------------------------------


async def test_me_returns_only_the_callers_own_record(client, db):
    world = await _world(client, db)
    await _name_users(db)
    resp = await client.get("/api/v1/users/me", headers=_auth(world.tokens["owner"]))
    assert resp.status_code == 200
    body = resp.json()
    assert (body["name"], body["email"], body["id"]) == (
        "Olivia Owner",
        "owner@example.com",
        world.owner_id,
    )
    assert "password_hash" not in body and "assigned_geofence_ids" not in body
    assert (await client.get("/api/v1/users/me")).status_code == 401


async def test_document_carries_owner_name_but_never_the_email(client, db):
    world = await _world(client, db)
    await _name_users(db)
    token = world.tokens["owner"]
    one = (await client.get(f"/api/v1/documents/{world.public_id}", headers=_auth(token))).json()
    assert one["owner_name"] == "Olivia Owner" and one["owner_id"] == world.owner_id
    listed = await client.get("/api/v1/documents", headers=_auth(token))
    assert {d["owner_name"] for d in listed.json()["items"]} == {"Olivia Owner"}
    assert "owner@example.com" not in listed.text


async def test_owner_name_does_not_open_a_hidden_document(client, db):
    world = await _world(client, db)
    await _name_users(db)
    for who in LOW_USERS:
        token = world.tokens[who]
        hidden = await client.get(f"/api/v1/documents/{world.secret_id}", headers=_auth(token))
        missing = await client.get(f"/api/v1/documents/{'0' * 24}", headers=_auth(token))
        assert hidden.status_code == missing.status_code == 404
        assert hidden.json() == missing.json()
        listed = await client.get("/api/v1/documents", headers=_auth(token))
        assert "Olivia Owner" in listed.text  # the public doc's owner, which they may see
        assert SECRET_TITLE not in listed.text


async def test_deleted_owner_leaves_no_name_and_the_id_remains(client, db):
    world = await _world(client, db)
    await db["users"].delete_one({"email": "owner@example.com"})
    resp = await client.get(
        f"/api/v1/documents/{world.public_id}", headers=_auth(world.tokens["admin"])
    )
    body = resp.json()
    assert body["owner_name"] is None and body["owner_id"] == world.owner_id


async def test_audit_rows_show_actor_and_target_names(client, db):
    world = await _world(client, db)
    await _name_users(db)
    resp = await client.get(
        "/api/v1/audit",
        headers=_auth(world.tokens["ts_auditor"]),
        params={"action": "LOGIN_SUCCESS", "limit": 100},
    )
    rows = {r["actor_id"]: r for r in resp.json()["items"]}
    assert rows[world.owner_id]["actor_label"] == "Olivia Owner"
    assert rows[world.owner_id]["actor_email"] == "owner@example.com"
    # LOGIN_SUCCESS targets the user, so the target is named too.
    assert rows[world.owner_id]["target_label"] == "Olivia Owner"


async def test_audit_failed_login_actor_is_the_typed_email_and_not_a_user(client, db):
    world = await _world(client, db)
    await client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "x"})
    resp = await client.get(
        "/api/v1/audit",
        headers=_auth(world.tokens["admin"]),
        params={"action": "LOGIN_FAILURE"},
    )
    row = resp.json()["items"][0]
    assert row["actor_label"] == "nobody@example.com" and row["actor_email"] is None


async def test_audit_document_title_label_respects_clearance(client, db):
    world = await _world(client, db)

    def labels(resp):
        rows = resp.json()["items"]
        return {r["target_label"] for r in rows if r["target_id"] == world.secret_id}

    params = {"document_id": world.secret_id, "limit": 100}
    low_token, high_token = world.tokens["auditor"], world.tokens["ts_auditor"]
    low = await client.get("/api/v1/audit", headers=_auth(low_token), params=params)
    high = await client.get("/api/v1/audit", headers=_auth(high_token), params=params)
    assert low.status_code == high.status_code == 200
    assert SECRET_TITLE not in low.text  # the rows are there, the title is withheld
    assert labels(low) == {None}
    assert SECRET_TITLE in labels(high)  # positive control: the title is findable when cleared
    assert low.json()["total"] == high.json()["total"] > 0


async def test_renamed_user_shows_the_current_name_and_deleted_user_the_id_only(client, db):
    world = await _world(client, db)
    await _name_users(db)
    await db["users"].update_one(
        {"email": "owner@example.com"}, {"$set": {"name": "Olivia Renamed"}}
    )
    token = world.tokens["admin"]
    params = {"actor_id": world.owner_id, "limit": 100}
    rows = (await client.get("/api/v1/audit", headers=_auth(token), params=params)).json()["items"]
    assert rows and {r["actor_label"] for r in rows} == {"Olivia Renamed"}
    await db["users"].delete_one({"email": "owner@example.com"})
    rows = (await client.get("/api/v1/audit", headers=_auth(token), params=params)).json()["items"]
    assert rows and {r["actor_label"] for r in rows} == {None}
    assert {r["actor_id"] for r in rows} == {world.owner_id}


# --- B: audit filters ---------------------------------------------------------------------


async def test_audit_actions_lists_the_recorded_actions(client, db):
    world = await _world(client, db)
    resp = await client.get("/api/v1/audit/actions", headers=_auth(world.tokens["auditor"]))
    assert resp.status_code == 200
    actions = resp.json()["actions"]
    assert "LOGIN_SUCCESS" in actions and actions == sorted(actions)
    denied = await client.get("/api/v1/audit/actions", headers=_auth(world.tokens["staff"]))
    assert denied.status_code == 403


async def test_audit_filter_by_actor_name_and_by_document_work_with_paging(client, db):
    world = await _world(client, db)
    await _name_users(db)
    token = world.tokens["admin"]
    by_name = await client.get(
        "/api/v1/audit", headers=_auth(token), params={"actor": "olivia", "limit": 1, "page": 2}
    )
    assert by_name.status_code == 200
    body = by_name.json()
    assert body["total"] >= 2 and body["page"] == 2 and len(body["items"]) == 1
    assert body["items"][0]["actor_id"] == world.owner_id

    both = await client.get(
        "/api/v1/audit",
        headers=_auth(token),
        params={"actor": "olivia", "action": "LOGIN_SUCCESS", "limit": 100},
    )
    assert {r["action"] for r in both.json()["items"]} == {"LOGIN_SUCCESS"}
    assert both.json()["total"] == 1

    none = await client.get(
        "/api/v1/audit", headers=_auth(token), params={"actor": "no-such-person"}
    )
    assert none.json()["total"] == 0

    doc = await client.get(
        "/api/v1/audit", headers=_auth(token), params={"document_id": world.public_id, "limit": 100}
    )
    assert doc.json()["total"] > 0
    assert world.secret_id not in doc.text


async def test_audit_actor_search_is_escaped_not_a_pattern(client, db):
    world = await _world(client, db)
    resp = await client.get(
        "/api/v1/audit", headers=_auth(world.tokens["admin"]), params={"actor": ".*"}
    )
    assert resp.status_code == 200 and resp.json()["total"] == 0


@pytest.mark.parametrize(
    "params",
    [
        {"document_id": "not-an-object-id"},
        {"actor": "a"},
        {"actor": "x" * 101},
        {"action": "bad action!"},
        {"action": "A" * 65},
        {"actor_id": "x" * 101},
        {"limit": 101},
    ],
)
async def test_audit_filter_values_are_validated(client, db, params):
    world = await _world(client, db)
    resp = await client.get("/api/v1/audit", headers=_auth(world.tokens["admin"]), params=params)
    assert resp.status_code == 422


async def test_audit_default_is_newest_first(client, db):
    world = await _world(client, db)
    resp = await client.get(
        "/api/v1/audit", headers=_auth(world.tokens["admin"]), params={"limit": 100}
    )
    stamps = [r["created_at"] for r in resp.json()["items"]]
    assert stamps == sorted(stamps, reverse=True)


# --- E: login attempts ----------------------------------------------------------------------


async def _fail(client, email):
    return await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "wrong-password"}
    )


async def test_login_failure_reports_attempt_count_up_to_the_limit_then_429(client, db):
    await _create_user_and_login(
        client, db, email="real@example.com", role=Role.AUTHORIZED_STAFF, fence_id="f"
    )
    seen = []
    for _ in range(5):
        resp = await _fail(client, "real@example.com")
        assert resp.status_code == 401
        seen.append(resp.json())
    assert [b["attempts"] for b in seen] == [1, 2, 3, 4, 5]
    assert {b["max_attempts"] for b in seen} == {5}
    assert seen[0]["detail"] == "Invalid email or password"
    locked = await _fail(client, "real@example.com")
    assert locked.status_code == 429
    assert 1 <= locked.json()["retry_after_sec"] <= 61
    assert locked.headers["retry-after"] == str(locked.json()["retry_after_sec"])
    assert "attempts" not in locked.json()


async def test_login_answers_are_identical_for_unknown_wrong_password_and_disabled(client, db):
    await _create_user_and_login(
        client, db, email="known@example.com", role=Role.AUTHORIZED_STAFF, fence_id="f"
    )
    await _create_user_and_login(
        client, db, email="off@example.com", role=Role.AUTHORIZED_STAFF, fence_id="f"
    )
    await db["users"].update_one({"email": "off@example.com"}, {"$set": {"is_active": False}})
    off = {"email": "off@example.com", "password": PASSWORD}  # the disabled user's CORRECT password
    unknown = await _fail(client, "ghost@example.com")
    wrong = await _fail(client, "known@example.com")
    disabled = await client.post("/api/v1/auth/login", json=off)
    assert unknown.status_code == wrong.status_code == disabled.status_code == 401
    assert unknown.json() == wrong.json() == disabled.json()
    # The count keeps rising for all three alike.
    assert (await _fail(client, "ghost@example.com")).json()["attempts"] == 2
    assert (await _fail(client, "known@example.com")).json()["attempts"] == 2
    assert (await client.post("/api/v1/auth/login", json=off)).json()["attempts"] == 2
    # An email that does not exist locks out exactly like one that does.
    for _ in range(2):
        await _fail(client, "ghost@example.com")
    assert (await _fail(client, "ghost@example.com")).json()["attempts"] == 5
    assert (await _fail(client, "ghost@example.com")).status_code == 429


async def test_successful_login_resets_the_count(client, db):
    await _create_user_and_login(
        client, db, email="reset@example.com", role=Role.AUTHORIZED_STAFF, fence_id="f"
    )
    await _fail(client, "reset@example.com")
    ok = await client.post(
        "/api/v1/auth/login", json={"email": "reset@example.com", "password": PASSWORD}
    )
    assert ok.status_code == 200
    assert (await _fail(client, "reset@example.com")).json()["attempts"] == 1


# --- C: explorer link and network label --------------------------------------------------------


async def test_etherscan_link_and_label_follow_the_configured_chain(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "CHAIN_ID", 11155111)
    assert blockchain_service.etherscan_url("0xabc") == "https://sepolia.etherscan.io/tx/0xabc"
    assert blockchain_service.network_label() == "Sepolia testnet"
    monkeypatch.setattr(settings, "CHAIN_ID", 31337)
    assert blockchain_service.etherscan_url("0xabc") is None
    assert "31337" in blockchain_service.network_label()


# --- D: counts reconcile --------------------------------------------------------------------


async def test_reports_total_minus_archived_equals_the_repository_total(client, db):
    from bson import ObjectId

    world = await _world(client, db)
    await db["documents"].update_one(
        {"_id": ObjectId(world.public_id)}, {"$set": {"status": "ARCHIVED"}}
    )
    token = world.tokens["ts_auditor"]
    summary = (await client.get("/api/v1/reports/summary", headers=_auth(token))).json()
    by_status = {r["status"]: r["count"] for r in summary["documents_by_status"]}
    listed = (await client.get("/api/v1/documents", headers=_auth(token))).json()
    archived = (
        await client.get("/api/v1/documents", headers=_auth(token), params={"status": "ARCHIVED"})
    ).json()
    assert archived["total"] == by_status["ARCHIVED"] == 1
    assert listed["total"] == sum(by_status.values()) - by_status["ARCHIVED"]
