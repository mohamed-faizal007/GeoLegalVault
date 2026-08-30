"""Tests for the append-only audit trail (Plan Parts 20, 32, Phase 8):
every security-relevant action writes exactly one audit_logs record,
the collection has no update/delete API path, /audit is Auditor/Admin-only,
and VERIFY_FAIL (Phase 7) and GEOFENCE_DENIED (Phase 3) both show up.
"""

import time

import pytest

from app.modules.users.models import Role
from app.modules.users.schemas import UserCreate
from app.modules.users.service import create_user
from app.services import storage
from tests.integration.test_anchor import local_chain  # noqa: F401 (reused fixture)
from tests.integration.test_verify import _activate_document  # noqa: F401 (reused helper)
from tests.integration.test_workflow import (  # noqa: F401 (reused helpers)
    PDF_BYTES,
    _auth,
    _create_fence,
    _create_user_and_login,
    _geo,
    _upload,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")

PASSWORD = "Str0ngPassw0rd!"


async def _login(client, db, email: str, role: Role) -> str:
    await create_user(db, UserCreate(email=email, password=PASSWORD, name="Test", role=role))
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def test_login_success_and_failure_each_write_one_audit_record(client, db):
    admin_token = await _login(client, db, "admin-audit@example.com", Role.ADMINISTRATOR)

    # Wrong password -> exactly one LOGIN_FAILURE record for that email.
    bad = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin-audit@example.com", "password": "wrong-password"},
    )
    assert bad.status_code == 401

    resp = await client.get(
        "/api/v1/audit", headers=_auth(admin_token), params={"action": "LOGIN_FAILURE"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    record = body["items"][0]
    assert record["action"] == "LOGIN_FAILURE"
    assert record["target_type"] == "user"
    assert record["result"] == "INVALID_CREDENTIALS"
    assert record["created_at"] is not None

    # And the earlier successful admin login produced its own record.
    success_resp = await client.get(
        "/api/v1/audit", headers=_auth(admin_token), params={"action": "LOGIN_SUCCESS"}
    )
    assert success_resp.status_code == 200
    success_body = success_resp.json()
    assert success_body["total"] == 1
    assert success_body["items"][0]["result"] == "SUCCESS"


async def test_non_auditor_non_admin_gets_403_on_audit(client, db):
    token = await _login(client, db, "staff-audit@example.com", Role.AUTHORIZED_STAFF)

    response = await client.get("/api/v1/audit", headers=_auth(token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_auditor_role_can_view_audit_logs(client, db):
    token = await _login(client, db, "auditor-audit@example.com", Role.AUDITOR)

    response = await client.get("/api/v1/audit", headers=_auth(token))
    assert response.status_code == 200
    body = response.json()
    assert "items" in body and "total" in body
    # The auditor's own login already wrote one LOGIN_SUCCESS record.
    assert body["total"] >= 1


async def test_audit_logs_have_no_update_or_delete_endpoint(client, db):
    token = await _login(client, db, "admin-noupdate@example.com", Role.ADMINISTRATOR)

    patch_resp = await client.patch(
        "/api/v1/audit/000000000000000000000000", headers=_auth(token), json={"result": "X"}
    )
    assert patch_resp.status_code in (404, 405)

    delete_resp = await client.delete(
        "/api/v1/audit/000000000000000000000000", headers=_auth(token)
    )
    assert delete_resp.status_code in (404, 405)

    # And the bare collection path itself has no non-GET method.
    delete_all_resp = await client.delete("/api/v1/audit", headers=_auth(token))
    assert delete_all_resp.status_code in (404, 405)


async def test_pagination_and_result_filter_work(client, db):
    token = await _login(client, db, "admin-page@example.com", Role.ADMINISTRATOR)

    for i in range(3):
        await client.post(
            "/api/v1/auth/login",
            json={"email": f"nonexistent-{i}@example.com", "password": "whatever"},
        )

    page1 = await client.get(
        "/api/v1/audit",
        headers=_auth(token),
        params={"action": "LOGIN_FAILURE", "page": 1, "limit": 2},
    )
    assert page1.status_code == 200
    body1 = page1.json()
    assert body1["total"] == 3
    assert len(body1["items"]) == 2

    page2 = await client.get(
        "/api/v1/audit",
        headers=_auth(token),
        params={"action": "LOGIN_FAILURE", "page": 2, "limit": 2},
    )
    assert len(page2.json()["items"]) == 1


async def test_geofence_denied_appears_in_audit(client, db):
    fence_id = await _create_fence(db)
    token = await _create_user_and_login(
        client, db, email="outside-audit@example.com", role=Role.AUTHORIZED_STAFF, fence_id=fence_id
    )
    admin_token = await _login(client, db, "admin-geo-audit@example.com", Role.ADMINISTRATOR)

    outside_geo = {
        "X-Geo-Lat": "11.00",
        "X-Geo-Lng": "77.00",
        "X-Geo-Accuracy": "10",
        "X-Geo-Timestamp": str(time.time()),
    }
    resp = await client.post(
        "/api/v1/documents",
        headers={**_auth(token), **outside_geo},
        data={
            "title": "Denied Upload",
            "doc_type": "CONTRACT",
            "classification": "RESTRICTED",
            "tags": "",
        },
        files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "GEOFENCE_DENIED"

    audit_resp = await client.get(
        "/api/v1/audit", headers=_auth(admin_token), params={"action": "GEOFENCE_DENIED"}
    )
    assert audit_resp.status_code == 200
    body = audit_resp.json()
    assert body["total"] == 1
    record = body["items"][0]
    assert record["result"] == "DENIED"
    assert record["location"]["coordinates"] == [77.00, 11.00]


async def test_upload_writes_an_audit_record(client, db):
    fence_id = await _create_fence(db)
    token = await _create_user_and_login(
        client,
        db,
        email="uploader-audit@example.com",
        role=Role.AUTHORIZED_STAFF,
        fence_id=fence_id,
    )
    admin_token = await _login(client, db, "admin-upload-audit@example.com", Role.ADMINISTRATOR)

    upload = await _upload(client, token)

    audit_resp = await client.get(
        "/api/v1/audit", headers=_auth(admin_token), params={"action": "UPLOAD"}
    )
    assert audit_resp.status_code == 200
    body = audit_resp.json()
    assert body["total"] == 1
    assert body["items"][0]["target_id"] == upload["document_id"]


async def test_verify_fail_appears_in_audit(client, db, local_chain):  # noqa: F811
    approver, _document_id, version_id, storage_key = await _activate_document(client, db)
    admin_token = await _login(client, db, "admin-verify-audit@example.com", Role.ADMINISTRATOR)

    tampered = PDF_BYTES[:-1] + bytes([PDF_BYTES[-1] ^ 0xFF])
    storage.put_object(tampered, storage_key, "application/pdf")

    resp = await client.post(f"/api/v1/verify/{version_id}", headers=_auth(approver))
    assert resp.status_code == 200, resp.text
    assert resp.json()["result"] == "MISMATCH"

    audit_resp = await client.get(
        "/api/v1/audit", headers=_auth(admin_token), params={"action": "VERIFY_FAIL"}
    )
    assert audit_resp.status_code == 200
    body = audit_resp.json()
    assert body["total"] == 1
    assert body["items"][0]["target_id"] == version_id
    assert body["items"][0]["result"] == "MISMATCH"
