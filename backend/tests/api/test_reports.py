"""Tests for GET /reports/summary (Plan Part 16, Phase 10): correct
aggregate counts on seeded data, and audit:view-only access (Administrator
+ Auditor — no new permission was invented for this).

Seeds each collection directly rather than driving full HTTP workflows —
the aggregation pipelines only care about a handful of fields per
collection, so this keeps the test focused and fast while still exercising
the real Mongo `$group` queries.
"""

from datetime import UTC, datetime

import pytest

from app.modules.audit.models import AUDIT_LOGS_COLLECTION
from app.modules.blockchain.models import BLOCKCHAIN_ANCHORS_COLLECTION
from app.modules.documents.models import DOCUMENTS_COLLECTION
from app.modules.users.models import Role
from app.modules.users.schemas import UserCreate
from app.modules.users.service import create_user
from app.modules.verify.models import VERIFICATION_RECORDS_COLLECTION

pytestmark = pytest.mark.asyncio(loop_scope="session")

PASSWORD = "Str0ngPassw0rd!"


async def _login(client, db, email: str, role: Role) -> str:
    await create_user(db, UserCreate(email=email, password=PASSWORD, name="Test", role=role))
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed_summary_fixtures(db) -> None:
    now = datetime.now(UTC)
    await db[DOCUMENTS_COLLECTION].insert_many(
        [
            {"status": "DRAFT", "doc_type": "CONTRACT", "created_at": now, "updated_at": now},
            {"status": "DRAFT", "doc_type": "MEMO", "created_at": now, "updated_at": now},
            {"status": "ACTIVE", "doc_type": "CONTRACT", "created_at": now, "updated_at": now},
            {"status": "ARCHIVED", "doc_type": "CONTRACT", "created_at": now, "updated_at": now},
        ]
    )
    await db[BLOCKCHAIN_ANCHORS_COLLECTION].insert_many(
        [
            {"status": "CONFIRMED", "created_at": now},
            {"status": "CONFIRMED", "created_at": now},
            {"status": "CONFIRMED", "created_at": now},
            {"status": "FAILED", "created_at": now},
            {"status": "PENDING", "created_at": now},
        ]
    )
    await db[VERIFICATION_RECORDS_COLLECTION].insert_many(
        [
            {"result": "VERIFIED", "created_at": now},
            {"result": "VERIFIED", "created_at": now},
            {"result": "MISMATCH", "created_at": now},
            {"result": "NOT_ANCHORED", "created_at": now},
        ]
    )
    await db[AUDIT_LOGS_COLLECTION].insert_many(
        [
            {"action": "GEOFENCE_DENIED", "created_at": now},
            {"action": "GEOFENCE_DENIED", "created_at": now},
            {"action": "LOGIN_SUCCESS", "created_at": now},
        ]
    )


async def test_summary_aggregates_match_seeded_data(client, db):
    await _seed_summary_fixtures(db)
    token = await _login(client, db, "admin-reports@example.com", Role.ADMINISTRATOR)

    resp = await client.get("/api/v1/reports/summary", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    by_status = {row["status"]: row["count"] for row in body["documents_by_status"]}
    assert by_status == {"DRAFT": 2, "ACTIVE": 1, "ARCHIVED": 1}

    by_doc_type = {row["doc_type"]: row["count"] for row in body["documents_by_doc_type"]}
    assert by_doc_type == {"CONTRACT": 3, "MEMO": 1}

    assert body["anchoring"] == {
        "pending": 1,
        "confirmed": 3,
        "failed": 1,
        "success_rate": pytest.approx(0.75),
    }

    assert body["verifications_recent"]["verified"] == 2
    assert body["verifications_recent"]["mismatch"] == 1
    assert body["verifications_recent"]["not_anchored"] == 1
    assert body["verifications_recent"]["window_days"] == 30

    assert body["geofence_denied_count"] == 2


async def test_summary_handles_empty_collections(client, db):
    token = await _login(client, db, "admin-reports-empty@example.com", Role.ADMINISTRATOR)

    resp = await client.get("/api/v1/reports/summary", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["documents_by_status"] == []
    assert body["documents_by_doc_type"] == []
    assert body["anchoring"] == {
        "pending": 0,
        "confirmed": 0,
        "failed": 0,
        "success_rate": 0.0,
    }
    assert body["geofence_denied_count"] == 0


async def test_auditor_can_view_summary(client, db):
    token = await _login(client, db, "auditor-reports@example.com", Role.AUDITOR)

    resp = await client.get("/api/v1/reports/summary", headers=_auth(token))
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize(
    "role",
    [Role.LEGAL_OFFICER, Role.REVIEWING_OFFICER, Role.AUTHORIZED_STAFF],
)
async def test_non_audit_roles_cannot_view_summary(client, db, role):
    token = await _login(client, db, f"{role.value.lower()}-reports@example.com", role)

    resp = await client.get("/api/v1/reports/summary", headers=_auth(token))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
