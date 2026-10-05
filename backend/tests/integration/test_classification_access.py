"""SEC-02 / D-051: a document is visible only to users whose clearance reaches its classification.

Every test has a hard timeout. Nothing reads `.env`: users, levels and chain settings are set
explicitly (the verify control uses a dead local port, never a real RPC). No transaction is sent.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from bson import ObjectId

from app.core.rbac import (
    ANCHOR_RETRY,
    APPROVE_PERFORM,
    DOCUMENT_AMEND,
    DOCUMENT_ARCHIVE,
    DOCUMENT_VIEW,
    INTEGRITY_CLEAR,
    REVIEW_PERFORM,
    VERIFY_PERFORM,
    has_permission,
)
from app.modules.users.models import Role
from tests.api.test_anchor_attention import ATTENTION, REASON, _stuck
from tests.integration.anchor_helpers import fast_anchor, hard_timeout  # noqa: F401
from tests.integration.chain_outage_helpers import (
    NO_CODE_ADDRESS,
    chain_env,  # noqa: F401 (fixture)
    dead_port_url,
)
from tests.integration.test_workflow import (
    PDF_BYTES,
    _auth,
    _create_fence,
    _create_user_and_login,
    _geo,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")

TS = "TOP_SECRET"
LOW = "INTERNAL"
LEVELS = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED", "TOP_SECRET"]
SECRET_TITLE = "Secret Merger Plan"
SECRET_COMMENT = "SECRET-REVIEW-COMMENT-9f3a"
HIDDEN_TITLE = "Restricted document"

USERS: dict[str, tuple[Role, str]] = {
    "owner": (Role.LEGAL_OFFICER, TS),
    "ts_reviewer": (Role.REVIEWING_OFFICER, TS),
    "ts_officer": (Role.LEGAL_OFFICER, TS),
    "ts_auditor": (Role.AUDITOR, TS),
    "staff": (Role.AUTHORIZED_STAFF, LOW),
    "reviewer": (Role.REVIEWING_OFFICER, LOW),
    "officer": (Role.LEGAL_OFFICER, LOW),
    "auditor": (Role.AUDITOR, LOW),
    "admin": (Role.ADMINISTRATOR, LOW),
}
LOW_USERS = ["staff", "reviewer", "officer", "auditor", "admin"]
CLEARED_USERS = ["owner", "ts_reviewer", "ts_officer", "ts_auditor"]


@dataclass
class World:
    tokens: dict[str, str]
    secret_id: str
    secret_version: str
    public_id: str
    public_version: str
    owner_id: str


async def _upload_as(
    client, token, classification, title, data=PDF_BYTES, amend_of=None, tags="merger,secret"
):
    form = {
        "title": title,
        "doc_type": "CONTRACT",
        "classification": classification,
        "tags": tags,
    }
    if amend_of:
        form["amend_of"] = amend_of
    return await client.post(
        "/api/v1/documents",
        headers={**_auth(token), **_geo()},
        data=form,
        files={"file": ("contract.pdf", data, "application/pdf")},
    )


async def _world(client, db) -> World:
    fence = await _create_fence(db)
    tokens = {}
    for key, (role, clearance) in USERS.items():
        tokens[key] = await _create_user_and_login(
            client,
            db,
            email=f"{key}@example.com",
            role=role,
            fence_id=fence,
            clearance=clearance,
        )
    secret = await _upload_as(client, tokens["owner"], TS, SECRET_TITLE, PDF_BYTES + b"-secret")
    assert secret.status_code == 201, secret.text
    public = await _upload_as(
        client, tokens["owner"], "PUBLIC", "Open Notice", PDF_BYTES + b"-pub", tags="notice"
    )
    assert public.status_code == 201, public.text
    owner = await db["users"].find_one({"email": "owner@example.com"})
    return World(
        tokens=tokens,
        secret_id=secret.json()["document_id"],
        secret_version=secret.json()["version_id"],
        public_id=public.json()["document_id"],
        public_version=public.json()["version_id"],
        owner_id=str(owner["_id"]),
    )


async def _insert_anchor(db, document_id: str, version_id: str) -> None:
    now = datetime.now(UTC)
    await db["blockchain_anchors"].insert_one(
        {
            "document_id": ObjectId(document_id),
            "version_id": ObjectId(version_id),
            "sha256": "ab" * 32,
            "event_type": 1,
            "block_number": 1,
            "contract_address": NO_CODE_ADDRESS,
            "network": "sepolia",
            "status": "CONFIRMED",
            "live": True,
            "error": None,
            "created_at": now,
            "confirmed_at": now,
        }
    )


async def _call(client, token, method, url, **kwargs):
    headers = {**_auth(token), **_geo()}
    return await client.request(method, url, headers=headers, **kwargs)


# (key, method, path template, permission the role needs, request kwargs)
PROBES = [
    ("detail", "GET", "/api/v1/documents/{d}", DOCUMENT_VIEW, {}),
    ("download", "GET", "/api/v1/documents/{d}/download", DOCUMENT_VIEW, {}),
    ("versions", "GET", "/api/v1/documents/{d}/versions", DOCUMENT_VIEW, {}),
    ("submit", "POST", "/api/v1/documents/{d}/submit", None, {}),
    (
        "review",
        "POST",
        "/api/v1/documents/{d}/review",
        REVIEW_PERFORM,
        {"json": {"decision": "approve"}},
    ),
    ("approve", "POST", "/api/v1/documents/{d}/approve", APPROVE_PERFORM, {}),
    (
        "amend",
        "POST",
        "/api/v1/documents/{d}/amend",
        DOCUMENT_AMEND,
        {"json": {"reason": "needs a change here"}},
    ),
    ("archive", "POST", "/api/v1/documents/{d}/archive", DOCUMENT_ARCHIVE, {}),
    (
        "clear",
        "POST",
        "/api/v1/documents/{d}/integrity/clear",
        INTEGRITY_CLEAR,
        {"json": {"reason": "Restored from the nightly backup."}},
    ),
    ("verify", "POST", "/api/v1/verify/{v}", VERIFY_PERFORM, {}),
    ("verify-history", "GET", "/api/v1/verify/{v}/history", VERIFY_PERFORM, {}),
    ("anchor", "GET", "/api/v1/blockchain/anchor/{v}", DOCUMENT_VIEW, {}),
    # The one carve-out (D-051): re-queueing an anchor never reveals content (Guardrail #3).
    (
        "retry",
        "POST",
        "/api/v1/blockchain/anchors/{d}/retry",
        ANCHOR_RETRY,
        {"json": {"reason": "Wallet funded again"}},
    ),
]
SUBMIT_PERMISSION = "document:submit"


def _permission(key: str, perm):
    return SUBMIT_PERMISSION if key == "submit" else perm


def _url(template: str, d: str, v: str) -> str:
    return template.format(d=d, v=v)


# --- an uncleared user cannot use a hidden document in any way -----------------------------


@pytest.mark.parametrize("user", LOW_USERS)
@hard_timeout(120)
async def test_a_user_without_clearance_cannot_reach_a_top_secret_document(
    client, db, user, monkeypatch
):
    from app.modules.documents import router as documents_router

    presigned: list[str] = []
    monkeypatch.setattr(
        documents_router,
        "generate_presigned_get",
        lambda key, *a, **k: presigned.append(key) or "http://example.invalid/never",
    )
    w = await _world(client, db)
    await _insert_anchor(db, w.secret_id, w.secret_version)
    role = Role(USERS[user][0])
    fake = str(ObjectId())

    for key, method, template, perm, kwargs in PROBES:
        hidden = await _call(
            client, w.tokens[user], method, _url(template, w.secret_id, w.secret_version), **kwargs
        )
        nonexistent = await _call(
            client, w.tokens[user], method, _url(template, fake, fake), **kwargs
        )
        label = f"{user} {method} {template}"
        assert hidden.status_code not in range(200, 300), f"{label} succeeded: {hidden.text}"
        needed = _permission(key, perm)
        if key == "retry" and has_permission(role.value, needed):
            # An administrator can re-queue what they cannot read; it is a non-2xx here only
            # because this document is not stuck.
            assert hidden.status_code in (404, 409), label
            continue
        expected = 404 if has_permission(role.value, needed) else 403
        assert hidden.status_code == expected, f"{label}: {hidden.status_code} {hidden.text}"
        # IDOR: a hidden id is indistinguishable from an id that does not exist.
        assert (hidden.status_code, hidden.json()) == (
            nonexistent.status_code,
            nonexistent.json(),
        ), f"{label} tells a hidden document from a nonexistent one"
    assert presigned == [], "a pre-signed URL was generated for a document the caller cannot see"


@pytest.mark.parametrize("user", LOW_USERS)
@hard_timeout(90)
async def test_a_hidden_document_is_absent_from_list_search_and_counts(client, db, user):
    w = await _world(client, db)
    token = w.tokens[user]

    listing = (await _call(client, token, "GET", "/api/v1/documents")).json()
    assert [i["title"] for i in listing["items"]] == ["Open Notice"]
    assert listing["total"] == 1
    for url in (
        "/api/v1/documents?query=Merger",
        "/api/v1/documents?query=secret",
        f"/api/v1/documents?owner={w.owner_id}&doc_type=CONTRACT",
        "/api/v1/documents?status=DRAFT",
    ):
        body = (await _call(client, token, "GET", url)).json()
        titles = [i["title"] for i in body["items"]]
        assert SECRET_TITLE not in titles, url
        assert SECRET_COMMENT not in json.dumps(body)
        if "query=" in url:
            assert body["total"] == 0, url
        else:
            assert body["total"] == 1, url


@hard_timeout(120)
async def test_cleared_users_and_public_documents_still_work(client, db, chain_env, monkeypatch):  # noqa: F811
    from app.modules.documents import router as documents_router

    presigned: list[str] = []
    monkeypatch.setattr(
        documents_router,
        "generate_presigned_get",
        lambda key, *a, **k: presigned.append(key) or "http://example.invalid/ok",
    )
    chain_env(
        SEPOLIA_RPC_URL=dead_port_url(),
        CONTRACT_ADDRESS=NO_CODE_ADDRESS,
        CHAIN_ID=31337,
        CHAIN_READ_TIMEOUT_SEC=2,
    )
    w = await _world(client, db)

    for user in CLEARED_USERS:
        listing = (await _call(client, w.tokens[user], "GET", "/api/v1/documents")).json()
        assert listing["total"] == 2, user
        hits = (await _call(client, w.tokens[user], "GET", "/api/v1/documents?query=Merger")).json()
        assert [i["title"] for i in hits["items"]] == [SECRET_TITLE], user
        for path in (
            f"/api/v1/documents/{w.secret_id}",
            f"/api/v1/documents/{w.secret_id}/versions",
        ):
            assert (await _call(client, w.tokens[user], "GET", path)).status_code == 200, (
                user,
                path,
            )
        download = await _call(
            client, w.tokens[user], "GET", f"/api/v1/documents/{w.secret_id}/download"
        )
        assert download.status_code == 200, (user, download.text)
        verdict = await _call(client, w.tokens[user], "POST", f"/api/v1/verify/{w.secret_version}")
        assert verdict.status_code == 200, (user, verdict.text)
        history = await _call(
            client, w.tokens[user], "GET", f"/api/v1/verify/{w.secret_version}/history"
        )
        assert history.status_code == 200, (user, history.text)
    assert len(presigned) == len(CLEARED_USERS)

    for user in LOW_USERS:
        assert (
            await _call(client, w.tokens[user], "GET", f"/api/v1/documents/{w.public_id}")
        ).status_code == 200
        assert (
            await _call(client, w.tokens[user], "GET", f"/api/v1/documents/{w.public_id}/versions")
        ).status_code == 200
        verdict = await _call(client, w.tokens[user], "POST", f"/api/v1/verify/{w.public_version}")
        assert verdict.status_code == 200, (user, verdict.text)


# --- the guard that stops a new endpoint from forgetting the check ------------------------


async def test_every_route_with_a_document_or_version_id_has_an_access_probe():
    from app.main import app

    found = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        if path.startswith("/api") and ("{document_id}" in path or "{version_id}" in path):
            for method in route.methods - {"HEAD", "OPTIONS"}:
                found.add(
                    (method, path.replace("{document_id}", "{d}").replace("{version_id}", "{v}"))
                )
    probed = {(method, template) for _k, method, template, _p, _kw in PROBES}
    assert found == probed, (
        "a route that takes a document or version id has no clearance probe: "
        f"unprobed={sorted(found - probed)} stale={sorted(probed - found)}"
    )


# --- classification values -------------------------------------------------------------------


@pytest.mark.parametrize(
    "value", ["", "Top Secret", "restricted", "SECRET", "TOP_SECRET ", "x" * 5000]
)
@hard_timeout(60)
async def test_an_invalid_classification_is_refused(client, db, value):
    w = await _world(client, db)

    resp = await _upload_as(client, w.tokens["owner"], value, "Bad label", PDF_BYTES + b"-bad")

    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "INVALID_CLASSIFICATION"


@hard_timeout(90)
async def test_every_level_is_accepted_and_nobody_uploads_above_their_clearance(client, db):
    w = await _world(client, db)
    for i, level in enumerate(LEVELS):
        ok = await _upload_as(
            client, w.tokens["owner"], level, f"Level {level}", PDF_BYTES + bytes([i])
        )
        assert ok.status_code == 201, (level, ok.text)

    staff = w.tokens["staff"]  # clearance INTERNAL
    for level in ("PUBLIC", "INTERNAL"):
        resp = await _upload_as(client, staff, level, f"Staff {level}", PDF_BYTES + level.encode())
        assert resp.status_code == 201, (level, resp.text)
    for level in ("CONFIDENTIAL", "RESTRICTED", "TOP_SECRET"):
        resp = await _upload_as(client, staff, level, f"Staff {level}", PDF_BYTES + level.encode())
        assert resp.status_code == 403, (level, resp.text)
        assert resp.json()["error"]["code"] == "CLASSIFICATION_NOT_ALLOWED"
    assert (
        await db["documents"].count_documents({"title": {"$regex": "^Staff (CONF|REST|TOP)"}}) == 0
    )


# --- classification cannot be downgraded -----------------------------------------------------


@hard_timeout(120)
async def test_the_classification_cannot_be_changed_by_amend_or_any_other_route(client, db):
    w = await _world(client, db)
    owner, reviewer = w.tokens["owner"], w.tokens["ts_reviewer"]
    assert (
        await _call(client, owner, "POST", f"/api/v1/documents/{w.secret_id}/submit")
    ).status_code == 200
    changes = await _call(
        client,
        reviewer,
        "POST",
        f"/api/v1/documents/{w.secret_id}/review",
        json={"decision": "changes_requested", "comment": SECRET_COMMENT},
    )
    assert changes.status_code == 200, changes.text

    downgrade = await _upload_as(
        client, owner, "PUBLIC", SECRET_TITLE, PDF_BYTES + b"-v2", w.secret_id
    )

    assert downgrade.status_code == 422, downgrade.text
    assert downgrade.json()["error"]["code"] == "CLASSIFICATION_IMMUTABLE"
    document = await db["documents"].find_one({"_id": ObjectId(w.secret_id)})
    assert document["classification"] == TS
    assert (
        await db["document_versions"].count_documents({"document_id": ObjectId(w.secret_id)}) == 1
    )
    refused = (
        await db["audit_logs"]
        .find({"action": "CLASSIFICATION_CHANGE_REFUSED", "target_id": ObjectId(w.secret_id)})
        .to_list(None)
    )
    assert len(refused) == 1 and refused[0]["meta"] == {"attempted": "PUBLIC"}

    same = await _upload_as(client, owner, TS, SECRET_TITLE, PDF_BYTES + b"-v2", w.secret_id)
    assert same.status_code == 201, same.text
    assert (await db["documents"].find_one({"_id": ObjectId(w.secret_id)}))["classification"] == TS

    for method in ("PATCH", "PUT", "DELETE"):
        resp = await _call(
            client,
            owner,
            method,
            f"/api/v1/documents/{w.secret_id}",
            json={"classification": "PUBLIC"},
        )
        assert resp.status_code in (404, 405), (method, resp.status_code)
    assert (await db["documents"].find_one({"_id": ObjectId(w.secret_id)}))["classification"] == TS


@hard_timeout(60)
async def test_a_user_who_cannot_see_the_document_cannot_amend_its_classification_either(
    client, db
):
    w = await _world(client, db)

    resp = await _upload_as(
        client, w.tokens["staff"], "PUBLIC", SECRET_TITLE, PDF_BYTES + b"-x", w.secret_id
    )

    assert resp.status_code == 404
    assert (await db["documents"].find_one({"_id": ObjectId(w.secret_id)}))["classification"] == TS


# --- maker-checker still works for the people who may see the document ----------------------


@hard_timeout(120)
async def test_maker_checker_still_applies_to_reviewers_who_are_cleared(client, db):
    w = await _world(client, db)
    owner = w.tokens["owner"]
    assert (
        await _call(client, owner, "POST", f"/api/v1/documents/{w.secret_id}/submit")
    ).status_code == 200

    uncleared = await _call(
        client,
        w.tokens["reviewer"],
        "POST",
        f"/api/v1/documents/{w.secret_id}/review",
        json={"decision": "approve"},
    )
    assert uncleared.status_code == 404

    cleared = await _call(
        client,
        w.tokens["ts_reviewer"],
        "POST",
        f"/api/v1/documents/{w.secret_id}/review",
        json={"decision": "approve"},
    )
    assert cleared.status_code == 200, cleared.text

    own = await _call(client, owner, "POST", f"/api/v1/documents/{w.secret_id}/approve")
    assert own.status_code == 403 and own.json()["error"]["code"] == "MAKER_CHECKER_VIOLATION"
    low = await _call(
        client, w.tokens["officer"], "POST", f"/api/v1/documents/{w.secret_id}/approve"
    )
    assert low.status_code == 404


# --- the audit trail --------------------------------------------------------------------------


@hard_timeout(90)
async def test_refused_access_is_audited_only_for_a_document_that_exists(client, db):
    w = await _world(client, db)
    staff = await db["users"].find_one({"email": "staff@example.com"})

    for _ in range(2):
        assert (
            await _call(client, w.tokens["staff"], "GET", f"/api/v1/documents/{w.secret_id}")
        ).status_code == 404
    assert (
        await _call(client, w.tokens["staff"], "GET", f"/api/v1/documents/{ObjectId()}")
    ).status_code == 404
    assert (
        await _call(client, w.tokens["staff"], "GET", f"/api/v1/documents/{w.secret_id}/download")
    ).status_code == 404

    rows = await db["audit_logs"].find({"action": "ACCESS_DENIED"}).to_list(None)
    assert len(rows) == 3  # two detail attempts + one download; the nonexistent id left no row
    assert {str(r["target_id"]) for r in rows} == {w.secret_id}
    assert {str(r["actor_id"]) for r in rows} == {str(staff["_id"])}
    assert {r["meta"]["endpoint"] for r in rows} == {"detail", "download"}


@hard_timeout(120)
async def test_audit_rows_for_a_hidden_document_keep_the_fact_but_not_the_content(client, db):
    w = await _world(client, db)
    owner, reviewer = w.tokens["owner"], w.tokens["ts_reviewer"]
    await _call(client, owner, "POST", f"/api/v1/documents/{w.secret_id}/submit")
    await _call(
        client,
        reviewer,
        "POST",
        f"/api/v1/documents/{w.secret_id}/review",
        json={"decision": "changes_requested", "comment": SECRET_COMMENT},
    )

    cleared = await _call(client, w.tokens["ts_auditor"], "GET", "/api/v1/audit?limit=100")
    assert cleared.status_code == 200
    assert SECRET_COMMENT in cleared.text  # a cleared auditor sees everything

    for user in ("auditor", "admin"):
        for url in ("/api/v1/audit?limit=100", f"/api/v1/audit?target_id={w.secret_id}&limit=100"):
            resp = await _call(client, w.tokens[user], "GET", url)
            assert resp.status_code == 200, (user, url)
            assert SECRET_COMMENT not in resp.text, (user, url)
            assert SECRET_TITLE not in resp.text
        rows = (
            await _call(
                client, w.tokens[user], "GET", f"/api/v1/audit?target_id={w.secret_id}&limit=100"
            )
        ).json()["items"]
        actions = {r["action"] for r in rows}
        assert {"UPLOAD", "SUBMIT", "CHANGES_REQ"} <= actions, (
            user,
            actions,
        )  # oversight is not blinded
        assert all(r["meta"] == {} and r["redacted"] is True for r in rows), user
        public_rows = (
            await _call(
                client, w.tokens[user], "GET", f"/api/v1/audit?target_id={w.public_id}&limit=100"
            )
        ).json()["items"]
        assert public_rows and all(r["redacted"] is False for r in public_rows), user


# --- clearance management ----------------------------------------------------------------------


@hard_timeout(90)
async def test_clearance_is_set_by_another_administrator_and_audited(client, db):
    w = await _world(client, db)
    admin, staff = w.tokens["admin"], await db["users"].find_one({"email": "staff@example.com"})
    admin_row = await db["users"].find_one({"email": "admin@example.com"})

    ok = await _call(
        client, admin, "PATCH", f"/api/v1/users/{staff['_id']}", json={"clearance": "CONFIDENTIAL"}
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["clearance"] == "CONFIDENTIAL"
    row = await db["audit_logs"].find_one({"action": "USER_UPDATE", "target_id": str(staff["_id"])})
    assert row["meta"]["clearance"] == {"from": LOW, "to": "CONFIDENTIAL"}

    own = await _call(
        client, admin, "PATCH", f"/api/v1/users/{admin_row['_id']}", json={"clearance": TS}
    )
    assert own.status_code == 403 and own.json()["error"]["code"] == "SELF_CLEARANCE_CHANGE"
    assert (await db["users"].find_one({"_id": admin_row["_id"]}))["clearance"] == LOW

    bad = await _call(
        client, admin, "PATCH", f"/api/v1/users/{staff['_id']}", json={"clearance": "SECRET"}
    )
    assert bad.status_code == 422

    non_admin = await _call(
        client,
        w.tokens["officer"],
        "PATCH",
        f"/api/v1/users/{staff['_id']}",
        json={"clearance": TS},
    )
    assert non_admin.status_code == 403

    # The change applies on the very next request.
    assert (
        await _call(client, w.tokens["staff"], "GET", f"/api/v1/documents/{w.secret_id}")
    ).status_code == 404
    await _call(client, admin, "PATCH", f"/api/v1/users/{staff['_id']}", json={"clearance": TS})
    assert (
        await _call(client, w.tokens["staff"], "GET", f"/api/v1/documents/{w.secret_id}")
    ).status_code == 200


@hard_timeout(60)
async def test_a_new_user_defaults_to_the_lowest_clearance(client, db):
    w = await _world(client, db)
    created = await _call(
        client,
        w.tokens["admin"],
        "POST",
        "/api/v1/users",
        json={
            "email": "new@example.com",
            "password": "Str0ngPassw0rd!",
            "name": "New",
            "role": "AUTHORIZED_STAFF",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["clearance"] == "PUBLIC"
    explicit = await _call(
        client,
        w.tokens["admin"],
        "POST",
        "/api/v1/users",
        json={
            "email": "new2@example.com",
            "password": "Str0ngPassw0rd!",
            "name": "New2",
            "role": "AUTHORIZED_STAFF",
            "clearance": "CONFIDENTIAL",
        },
    )
    assert explicit.json()["clearance"] == "CONFIDENTIAL"


@hard_timeout(60)
async def test_a_user_without_a_clearance_field_or_a_bad_one_sees_only_public(client, db):
    w = await _world(client, db)
    await db["users"].update_one({"email": "staff@example.com"}, {"$unset": {"clearance": ""}})
    listing = (await _call(client, w.tokens["staff"], "GET", "/api/v1/documents")).json()
    assert [i["title"] for i in listing["items"]] == ["Open Notice"]

    await db["users"].update_one(
        {"email": "staff@example.com"}, {"$set": {"clearance": "GOD_MODE"}}
    )
    listing = (await _call(client, w.tokens["staff"], "GET", "/api/v1/documents")).json()
    assert [i["title"] for i in listing["items"]] == ["Open Notice"]


@hard_timeout(60)
async def test_a_document_with_an_unrecognised_classification_is_hidden_from_everyone(client, db):
    w = await _world(client, db)
    await db["documents"].update_one(
        {"_id": ObjectId(w.public_id)}, {"$set": {"classification": "Top Secret"}}
    )
    for user in ("owner", "ts_auditor", "admin", "staff"):
        listing = (await _call(client, w.tokens[user], "GET", "/api/v1/documents")).json()
        assert "Open Notice" not in [i["title"] for i in listing["items"]], user
        resp = await _call(client, w.tokens[user], "GET", f"/api/v1/documents/{w.public_id}")
        assert resp.status_code == 404, user


# --- reports ------------------------------------------------------------------------------------


@hard_timeout(90)
async def test_report_counts_only_include_documents_the_viewer_may_see(client, db):
    w = await _world(client, db)
    now = datetime.now(UTC)
    for version_id, document_id in (
        (w.secret_version, w.secret_id),
        (w.public_version, w.public_id),
    ):
        await _insert_anchor(db, document_id, version_id)
        await db["verification_records"].insert_one(
            {
                "version_id": ObjectId(version_id),
                "requested_by": ObjectId(w.owner_id),
                "recomputed_hash": "aa",
                "stored_hash": "aa",
                "onchain_hash": "aa",
                "result": "VERIFIED",
                "created_at": now,
            }
        )

    for user, expected in (("auditor", 1), ("admin", 1), ("ts_auditor", 2)):
        body = (await _call(client, w.tokens[user], "GET", "/api/v1/reports/summary")).json()
        assert sum(r["count"] for r in body["documents_by_status"]) == expected, user
        assert sum(r["count"] for r in body["documents_by_doc_type"]) == expected, user
        assert body["verifications_recent"]["verified"] == expected, user
        assert body["anchoring"]["confirmed"] == expected, user


# --- the stuck-anchor list: visible to operators, with the title withheld -----------------------


@hard_timeout(150)
async def test_the_stuck_anchor_list_withholds_titles_above_clearance_but_retry_still_works(
    client,
    db,
    fast_anchor,  # noqa: F811
):
    ctx = await _stuck(client, db)
    document_id = ctx["document_id"]
    await db["documents"].update_one(
        {"_id": ObjectId(document_id)}, {"$set": {"classification": TS, "title": SECRET_TITLE}}
    )
    await db["users"].update_one({"email": "admin@example.com"}, {"$set": {"clearance": LOW}})

    low = await client.get(ATTENTION, headers=_auth(ctx["admin"]))
    assert low.status_code == 200
    (item,) = low.json()["items"]
    assert item["document_id"] == document_id
    assert item["title"] == HIDDEN_TITLE
    assert SECRET_TITLE not in low.text

    retried = await client.post(
        f"/api/v1/blockchain/anchors/{document_id}/retry",
        headers={**_auth(ctx["admin"]), **_geo()},
        json={"reason": REASON},
    )
    assert retried.status_code == 200, retried.text
    assert SECRET_TITLE not in retried.text

    await db["users"].update_one({"email": "admin@example.com"}, {"$set": {"clearance": TS}})
    cleared = (await client.get(ATTENTION, headers=_auth(ctx["admin"]))).json()["items"]
    assert [i["title"] for i in cleared] == [SECRET_TITLE]
