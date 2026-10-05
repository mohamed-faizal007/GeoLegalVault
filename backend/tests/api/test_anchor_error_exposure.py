"""D-020 regression: a failed anchor must never leak the RPC URL / API key
through the anchor endpoint, the audit trail, or what is stored."""

import logging
from datetime import UTC, datetime

import pytest
from bson import ObjectId

from app.core.config import get_settings
from app.modules.blockchain import service as blockchain_service
from app.modules.users.models import Role
from app.modules.users.schemas import UserCreate
from app.modules.users.service import create_user
from app.services import blockchain as chain

pytestmark = pytest.mark.asyncio(loop_scope="session")

_KEY = "SUPERSECRETKEY123456"
_LEAKY = (
    "HTTPSConnectionPool(host='eth-sepolia.g.alchemy.com', port=443): "
    f"Max retries exceeded with url: /v2/{_KEY} (Caused by NewConnectionError('refused'))"
)


async def _login(client, db, role: Role) -> str:
    email = f"{role.value.lower()}@example.com"
    await create_user(
        db, UserCreate(
            email=email, password="Str0ngPassw0rd!", name="U", role=role, clearance="RESTRICTED"
        ),
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Str0ngPassw0rd!"}
    )
    return resp.json()["access_token"]


async def _version(db, version_id: ObjectId, document_id: ObjectId) -> None:
    # The anchor API resolves a version through its document (D-051), so the document must exist.
    await db["documents"].insert_one(
        {"_id": document_id, "title": "Doc", "classification": "PUBLIC", "status": "ACTIVE"}
    )
    await db["document_versions"].insert_one(
        {
            "_id": version_id,
            "document_id": document_id,
            "version_no": 1,
            "sha256": "ab" * 32,
            "storage_key": f"docs/{document_id}/v1",
            "size_bytes": 1,
            "mime": "application/pdf",
            "status": "APPROVED",
            "uploaded_by": ObjectId(),
            "uploaded_at": datetime.now(UTC),
            "anchored": False,
            "anchor_id": None,
        }
    )


async def test_failed_anchor_is_stored_logged_and_served_without_the_rpc_key(
    client, db, monkeypatch, caplog
):
    monkeypatch.setattr(
        get_settings(), "SEPOLIA_RPC_URL", f"https://eth-sepolia.g.alchemy.com/v2/{_KEY}"
    )

    async def _boom(*_args, **_kwargs):
        raise ConnectionError(_LEAKY)

    monkeypatch.setattr(chain, "anchor_hash", _boom)

    document_id, version_id = ObjectId(), ObjectId()
    await _version(db, version_id, document_id)
    with caplog.at_level(logging.ERROR):
        anchor = await blockchain_service.anchor_document_version(
            db,
            document_id=document_id,
            version_id=version_id,
            version_no=1,
            sha256="ab" * 32,
            event_type=1,
        )

    assert anchor["status"] == "FAILED"
    assert anchor["error"] == "RPC_UNREACHABLE"
    stored = await db["blockchain_anchors"].find_one({"_id": anchor["_id"]})
    assert _KEY not in str(stored)

    # Server-side log keeps useful detail but masks the key.
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "Max retries exceeded" in logged
    assert _KEY not in logged

    for role in (Role.REVIEWING_OFFICER, Role.AUDITOR):
        token = await _login(client, db, role)
        resp = await client.get(
            f"/api/v1/blockchain/anchor/{version_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["error"] == "RPC_UNREACHABLE"
        assert _KEY not in resp.text


async def test_legacy_anchor_rows_with_raw_error_text_are_sanitised_on_read(client, db):
    version_id, document_id = ObjectId(), ObjectId()
    await _version(db, version_id, document_id)
    await db["blockchain_anchors"].insert_one(
        {
            "document_id": document_id,
            "version_id": version_id,
            "sha256": "ab" * 32,
            "event_type": 1,
            "block_number": None,
            "contract_address": "0xabc",
            "network": "sepolia",
            "status": "FAILED",
            "error": _LEAKY,  # written before D-020
            "created_at": datetime.now(UTC),
            "confirmed_at": None,
        }
    )
    token = await _login(client, db, Role.AUDITOR)
    resp = await client.get(
        f"/api/v1/blockchain/anchor/{version_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["error"] == "ANCHOR_FAILED"
    assert _KEY not in resp.text
