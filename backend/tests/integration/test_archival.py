"""Archival tests (Plan Part 16, Phase 10): archiving hides a document from
the default repository view but it stays reachable via an explicit
status=ARCHIVED filter, and all of its versions + anchors are retained
untouched — it's still independently verifiable afterwards.
"""

import pytest

from tests.integration.test_anchor import local_chain  # noqa: F401 (reused fixture)
from tests.integration.test_verify import _activate_document  # noqa: F401 (reused helper)
from tests.integration.test_workflow import _auth  # noqa: F401 (reused helper)

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_archive_hides_from_default_list_but_retains_versions_and_anchors(
    client, db, local_chain  # noqa: F811
):
    approver, document_id, version_id, _storage_key = await _activate_document(client, db)

    archive_resp = await client.post(
        f"/api/v1/documents/{document_id}/archive", headers=_auth(approver)
    )
    assert archive_resp.status_code == 200, archive_resp.text
    assert archive_resp.json()["status"] == "ARCHIVED"

    default_list = await client.get("/api/v1/documents", headers=_auth(approver))
    assert default_list.status_code == 200
    assert document_id not in {item["id"] for item in default_list.json()["items"]}

    archived_list = await client.get(
        "/api/v1/documents", headers=_auth(approver), params={"status": "ARCHIVED"}
    )
    assert archived_list.status_code == 200
    assert document_id in {item["id"] for item in archived_list.json()["items"]}

    # Direct fetch by id (not the list view) still works regardless of status.
    direct = await client.get(f"/api/v1/documents/{document_id}", headers=_auth(approver))
    assert direct.status_code == 200
    assert direct.json()["status"] == "ARCHIVED"

    # Versions + anchor are untouched — still fully verifiable after archival.
    versions = await client.get(
        f"/api/v1/documents/{document_id}/versions", headers=_auth(approver)
    )
    assert versions.status_code == 200
    items = versions.json()["items"]
    assert len(items) == 1
    assert items[0]["anchored"] is True
    assert items[0]["anchor_id"] is not None

    verify_resp = await client.post(f"/api/v1/verify/{version_id}", headers=_auth(approver))
    assert verify_resp.status_code == 200, verify_resp.text
    assert verify_resp.json()["result"] == "VERIFIED"
