"""SEC-02 / D-052: the leak sweep. Every endpoint the UI pages call (dashboard counts and recent
documents, repository filters and search, document page, version history, verification page and
its history, blockchain page, anchor-attention banner, audit log, reports) is called as every
below-clearance role against a TOP_SECRET document, and no response may contain anything that
identifies it: title, tags, review comment, hash, storage key, document or version id (the audit
log's target id is the one place an id is allowed, by design, and its row must be marked redacted
with empty `meta`).

Runs against the throwaway test database; nothing reads `.env`; no transaction is sent.
"""

import pytest
from bson import ObjectId

from tests.integration.anchor_helpers import fast_anchor, hard_timeout  # noqa: F401
from tests.integration.chain_outage_helpers import chain_env  # noqa: F401 (fixture)
from tests.integration.test_classification_access import (
    LOW_USERS,
    SECRET_COMMENT,
    SECRET_TITLE,
    _call,
    _insert_anchor,
    _world,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


@hard_timeout(180)
async def test_no_ui_endpoint_leaks_a_hidden_document_to_a_below_clearance_role(
    client,
    db,
    chain_env,  # noqa: F811
):
    w = await _world(client, db)
    await _insert_anchor(db, w.secret_id, w.secret_version)
    assert (
        await _call(client, w.tokens["owner"], "POST", f"/api/v1/documents/{w.secret_id}/submit")
    ).status_code == 200
    review = await _call(
        client,
        w.tokens["ts_reviewer"],
        "POST",
        f"/api/v1/documents/{w.secret_id}/review",
        json={"decision": "changes_requested", "comment": SECRET_COMMENT},
    )
    assert review.status_code == 200, review.text

    version = await db["document_versions"].find_one({"_id": ObjectId(w.secret_version)})
    markers = [
        SECRET_TITLE,
        SECRET_COMMENT,
        "merger",
        version["sha256"],
        version["storage_key"],
        "ab" * 32,  # the anchor's hash
        w.secret_id,
        w.secret_version,
    ]
    ui_calls = [
        ("GET", "/api/v1/documents?limit=1"),  # dashboard total
        ("GET", "/api/v1/documents?limit=5"),  # dashboard recent
        ("GET", f"/api/v1/documents?owner={w.owner_id}&status=DRAFT&limit=1"),
        ("GET", "/api/v1/documents?status=UNDER_REVIEW&limit=1"),
        ("GET", "/api/v1/documents?status=CHANGES_REQUESTED&limit=25"),
        ("GET", "/api/v1/documents?query=Merger"),
        ("GET", "/api/v1/documents?query=secret"),
        ("GET", f"/api/v1/documents?owner={w.owner_id}&doc_type=CONTRACT&page=1"),
        ("GET", f"/api/v1/documents/{w.secret_id}"),
        ("GET", f"/api/v1/documents/{w.secret_id}/versions"),
        ("GET", f"/api/v1/verify/{w.secret_version}/history"),
        ("POST", f"/api/v1/verify/{w.secret_version}"),
        ("GET", f"/api/v1/blockchain/anchor/{w.secret_version}"),
        ("GET", "/api/v1/blockchain/anchors/attention"),
        ("GET", "/api/v1/reports/summary"),
    ]
    # Positive control: the same calls as a cleared user DO contain the markers, so an empty
    # result below means the data was withheld and not that the markers cannot be found.
    cleared = w.tokens["ts_officer"]
    seen = ""
    for method, url in ui_calls:
        seen += (await _call(client, cleared, method, url)).text.lower()
    for marker in (SECRET_TITLE, "merger", version["sha256"], w.secret_id, w.secret_version):
        assert marker.lower() in seen, marker

    for user in LOW_USERS:
        token = w.tokens[user]
        for method, url in ui_calls:
            resp = await _call(client, token, method, url)
            assert resp.status_code < 500, (user, url, resp.status_code)
            for marker in markers:
                assert marker.lower() not in resp.text.lower(), (user, url, marker)

        # The list the dashboard counts from: the hidden document is not in it, nor in the total.
        listing = (await _call(client, token, "GET", "/api/v1/documents?limit=25")).json()
        assert [d["title"] for d in listing["items"]] == ["Open Notice"], user
        assert listing["total"] == 1, user

    # The audit log: auditors and administrators see the row (oversight is not blinded), but the
    # row is marked redacted and carries no `meta`; no other text of the secret document appears.
    for user in ("auditor", "admin"):
        audit = await _call(client, w.tokens[user], "GET", "/api/v1/audit?limit=100")
        assert audit.status_code == 200, audit.text
        body = audit.json()
        rows = [r for r in body["items"] if r["target_id"] in (w.secret_id, w.secret_version)]
        assert rows, user
        for row in rows:
            assert row["redacted"] is True, (user, row["action"])
            assert row["meta"] == {}, (user, row["action"])
        for marker in markers[:6]:
            assert marker.lower() not in audit.text.lower(), (user, marker)
