"""API-level security regression tests for Phase 11's explicit checklist:
expired JWT, alg=none, IDOR, NoSQL-injection-shaped query params, malicious
filenames, and bad uploads. Oversized-file (413) and MIME-mismatch (422)
are already covered by tests/integration/test_upload.py and are not
duplicated here.
"""

import base64
import json
import time
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import TokenType
from app.modules.geofences.schemas import GeofenceCreate, GeoJSONPolygon
from app.modules.geofences.service import create_geofence
from app.modules.users.models import Role
from app.modules.users.schemas import UserCreate
from app.modules.users.service import create_user

pytestmark = pytest.mark.asyncio(loop_scope="session")

PASSWORD = "Str0ngPassw0rd!"
HQ_RING = [
    [78.14, 11.66],
    [78.16, 11.66],
    [78.16, 11.68],
    [78.14, 11.68],
    [78.14, 11.66],
]
PDF_BYTES = b"%PDF-1.4\n%mock pdf content for testing\n" + b"A" * 200


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _geo() -> dict:
    return {
        "X-Geo-Lat": "11.67",
        "X-Geo-Lng": "78.15",
        "X-Geo-Accuracy": "10",
        "X-Geo-Timestamp": str(time.time()),
    }


async def _create_fence(db) -> str:
    fence = await create_geofence(
        db, GeofenceCreate(name="HQ", region=GeoJSONPolygon(coordinates=[HQ_RING]))
    )
    return fence.id


async def _create_user_and_login(
    client, db, *, email: str, role, fence_id: str | None = None
) -> str:
    await create_user(
        db,
        UserCreate(
            email=email,
            password=PASSWORD,
            name=email,
            role=role,
            assigned_geofence_ids=[fence_id] if fence_id else [],
        ),
    )
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# --- Expired JWT -------------------------------------------------------------


async def test_expired_access_token_rejected_at_api_level(client, db):
    await create_user(
        db,
        UserCreate(
            email="expiry@example.com", password=PASSWORD, name="T", role=Role.ADMINISTRATOR
        ),
    )
    settings = get_settings()
    now = datetime.now(UTC)
    expired_payload = {
        "sub": "000000000000000000000000",
        "role": "ADMINISTRATOR",
        "iat": now - timedelta(minutes=30),
        "exp": now - timedelta(minutes=1),
        "jti": "expired-jti",
        "type": TokenType.ACCESS,
    }
    expired_token = jwt.encode(expired_payload, settings.JWT_SECRET, algorithm="HS256")

    response = await client.get("/api/v1/users", headers=_auth(expired_token))
    assert response.status_code == 401


# --- alg=none ----------------------------------------------------------------


async def test_alg_none_token_rejected_at_api_level(client, db):
    """A forged token claiming ADMINISTRATOR via the unsigned `alg: none`
    trick must never grant access, regardless of which user id or role it
    claims — the algorithm itself must be pinned server-side."""
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "none", "typ": "JWT"}).encode()
    ).rstrip(b"=")
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {
                "sub": "000000000000000000000000",
                "role": "ADMINISTRATOR",
                "jti": "forged",
                "type": TokenType.ACCESS,
                "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
            }
        ).encode()
    ).rstrip(b"=")
    forged_token = f"{header.decode()}.{payload.decode()}."

    response = await client.get("/api/v1/users", headers=_auth(forged_token))
    assert response.status_code == 401


# --- IDOR ---------------------------------------------------------------------


async def test_non_owner_cannot_submit_another_users_draft(client, db):
    """Object-level authorization: guessing/knowing another user's document
    id must not let a different user act on it as though they owned it.
    This app models "owner-only" as part of the lifecycle state machine
    (workflow.submit) rather than a generic RBAC permission, so the blocked
    attempt surfaces as 409 ILLEGAL_TRANSITION rather than a bare 403 — the
    object reference is still rejected, just with this app's own error
    taxonomy for "not a legal actor for this transition"."""
    fence_id = await _create_fence(db)
    owner_token = await _create_user_and_login(
        client, db, email="owner@example.com", role=Role.AUTHORIZED_STAFF, fence_id=fence_id
    )
    other_token = await _create_user_and_login(
        client, db, email="other-staff@example.com", role=Role.AUTHORIZED_STAFF, fence_id=fence_id
    )

    upload = await client.post(
        "/api/v1/documents",
        headers={**_auth(owner_token), **_geo()},
        data={"title": "Owner Doc", "doc_type": "CONTRACT", "classification": "RESTRICTED"},
        files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
    )
    assert upload.status_code == 201
    document_id = upload.json()["document_id"]

    forged_submit = await client.post(
        f"/api/v1/documents/{document_id}/submit", headers=_auth(other_token)
    )
    assert forged_submit.status_code == 409
    assert forged_submit.json()["error"]["code"] == "ILLEGAL_TRANSITION"

    # The document is untouched — still DRAFT, not silently advanced.
    doc = await client.get(f"/api/v1/documents/{document_id}", headers=_auth(owner_token))
    assert doc.json()["status"] == "DRAFT"


async def test_nonexistent_document_id_returns_404_not_a_crash(client, db):
    fence_id = await _create_fence(db)
    token = await _create_user_and_login(
        client, db, email="viewer-idor@example.com", role=Role.AUDITOR, fence_id=fence_id
    )

    response = await client.get(
        "/api/v1/documents/000000000000000000000000", headers=_auth(token)
    )
    assert response.status_code == 404


# --- NoSQL-injection-shaped query params --------------------------------------


async def test_operator_shaped_query_params_are_treated_as_literal_strings(client, db):
    """FastAPI/Pydantic query params are always plain strings, and this
    service never json.loads()'s one into a Mongo operator — so a value
    that *looks* like an operator (e.g. a literal '{"$ne": null}' string)
    can only ever match a doc_type/status/etc. that is that exact string,
    never bypass the filter. Confirms: no crash, no unintended matches."""
    fence_id = await _create_fence(db)
    token = await _create_user_and_login(
        client, db, email="injector@example.com", role=Role.AUTHORIZED_STAFF, fence_id=fence_id
    )
    await client.post(
        "/api/v1/documents",
        headers={**_auth(token), **_geo()},
        data={"title": "Real Doc", "doc_type": "CONTRACT", "classification": "PUBLIC"},
        files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
    )

    injection_payloads = [
        '{"$ne": null}',
        '{"$gt": ""}',
        "'; DROP TABLE documents; --",
        "$where:1==1",
    ]
    for payload in injection_payloads:
        response = await client.get(
            "/api/v1/documents",
            headers=_auth(token),
            params={"status": payload},
        )
        assert response.status_code == 200, response.text
        # A literal (nonsense) status string matches nothing real.
        assert response.json()["total"] == 0

        owner_response = await client.get(
            "/api/v1/documents",
            headers=_auth(token),
            params={"owner": payload},
        )
        assert owner_response.status_code == 200, owner_response.text
        assert owner_response.json()["total"] == 0


# --- Malicious filename --------------------------------------------------------


async def test_malicious_filename_never_reaches_the_storage_key(client, db):
    """The storage key is always server-generated (docs/{document_id}/v{n})
    — the client's filename is never read for that purpose anywhere in the
    upload path, so a path-traversal-shaped filename can't escape the
    document's own storage prefix."""
    fence_id = await _create_fence(db)
    token = await _create_user_and_login(
        client,
        db,
        email="filename-attack@example.com",
        role=Role.AUTHORIZED_STAFF,
        fence_id=fence_id,
    )

    malicious_name = "../../../../etc/passwd.pdf"
    upload = await client.post(
        "/api/v1/documents",
        headers={**_auth(token), **_geo()},
        data={"title": "Traversal Test", "doc_type": "CONTRACT", "classification": "PUBLIC"},
        files={"file": (malicious_name, PDF_BYTES, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document_id"]

    versions = await client.get(
        f"/api/v1/documents/{document_id}/versions", headers=_auth(token)
    )
    storage_key = versions.json()["items"][0]["storage_key"]
    assert storage_key == f"docs/{document_id}/v1"
    assert ".." not in storage_key
    assert "etc/passwd" not in storage_key
