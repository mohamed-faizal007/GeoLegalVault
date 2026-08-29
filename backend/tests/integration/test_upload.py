"""Integration tests for the upload -> store -> hash -> metadata flow.

Runs against the real local MinIO and Mongo the docker-compose stack
provides (no mocking layer, matching the rest of this test suite).
"""

import hashlib
import time

import httpx
import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.modules.documents import service as documents_service
from app.modules.geofences.schemas import GeofenceCreate, GeoJSONPolygon
from app.modules.geofences.service import create_geofence
from app.modules.users.models import Role
from app.modules.users.schemas import UserCreate
from app.modules.users.service import create_user
from app.modules.versions import service as versions_service
from app.services import storage

pytestmark = pytest.mark.asyncio(loop_scope="session")

HQ_RING = [
    [78.14, 11.66],
    [78.16, 11.66],
    [78.16, 11.68],
    [78.14, 11.68],
    [78.14, 11.66],
]
INSIDE_HEADERS = {"X-Geo-Lat": "11.67", "X-Geo-Lng": "78.15", "X-Geo-Accuracy": "10"}
OUTSIDE_HEADERS = {"X-Geo-Lat": "11.00", "X-Geo-Lng": "77.00", "X-Geo-Accuracy": "10"}

PDF_BYTES = b"%PDF-1.4\n%mock pdf content for testing\n" + b"A" * 200
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c48900000010494441545889636064606060000000050001a5f645"
    "0000000049454e44ae426082"
)


def _ts_header() -> dict:
    return {"X-Geo-Timestamp": str(time.time())}


async def _uploader_token(client, db) -> str:
    fence = await create_geofence(
        db, GeofenceCreate(name="HQ", region=GeoJSONPolygon(coordinates=[HQ_RING]))
    )
    await create_user(
        db,
        UserCreate(
            email="uploader@example.com",
            password="Str0ngPassw0rd!",
            name="Uploader",
            role=Role.AUTHORIZED_STAFF,
            assigned_geofence_ids=[fence.id],
        ),
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "uploader@example.com", "password": "Str0ngPassw0rd!"},
    )
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_valid_pdf_upload_returns_201_with_hash_and_draft_v1(client, db):
    token = await _uploader_token(client, db)
    headers = {**_auth(token), **INSIDE_HEADERS, **_ts_header()}

    response = await client.post(
        "/api/v1/documents",
        headers=headers,
        data={
            "title": "Vendor NDA",
            "doc_type": "CONTRACT",
            "classification": "RESTRICTED",
            "tags": "nda,vendor",
        },
        files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["sha256"] == hashlib.sha256(PDF_BYTES).hexdigest()

    doc_resp = await client.get(f"/api/v1/documents/{body['document_id']}", headers=_auth(token))
    assert doc_resp.status_code == 200
    assert doc_resp.json()["title"] == "Vendor NDA"
    assert doc_resp.json()["current_version_id"] == body["version_id"]

    versions_resp = await client.get(
        f"/api/v1/documents/{body['document_id']}/versions", headers=_auth(token)
    )
    assert versions_resp.status_code == 200
    versions = versions_resp.json()["items"]
    assert len(versions) == 1
    assert versions[0]["version_no"] == 1
    assert versions[0]["prev_version_hash"] is None
    assert versions[0]["storage_key"] == f"docs/{body['document_id']}/v1"


async def test_upload_outside_geofence_denied(client, db):
    token = await _uploader_token(client, db)
    headers = {**_auth(token), **OUTSIDE_HEADERS, **_ts_header()}

    response = await client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": "X", "doc_type": "CONTRACT", "classification": "PUBLIC"},
        files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "GEOFENCE_DENIED"


async def test_oversized_file_rejected(client, db):
    token = await _uploader_token(client, db)
    headers = {**_auth(token), **INSIDE_HEADERS, **_ts_header()}

    oversized = b"%PDF-1.4\n" + b"A" * (11 * 1024 * 1024)  # over the 10MB default cap
    response = await client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": "Big", "doc_type": "CONTRACT", "classification": "PUBLIC"},
        files={"file": ("big.pdf", oversized, "application/pdf")},
    )
    assert response.status_code == 413


async def test_mime_magic_mismatch_rejected(client, db):
    token = await _uploader_token(client, db)
    headers = {**_auth(token), **INSIDE_HEADERS, **_ts_header()}

    response = await client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": "Fake", "doc_type": "CONTRACT", "classification": "PUBLIC"},
        files={"file": ("fake.pdf", b"just plain text, not a pdf at all", "application/pdf")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MIME_MISMATCH"


async def test_unsupported_content_type_rejected(client, db):
    token = await _uploader_token(client, db)
    headers = {**_auth(token), **INSIDE_HEADERS, **_ts_header()}

    response = await client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": "Exe", "doc_type": "CONTRACT", "classification": "PUBLIC"},
        files={"file": ("virus.exe", b"MZ\x90\x00" + b"A" * 100, "application/x-msdownload")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


async def test_png_upload_also_works(client, db):
    token = await _uploader_token(client, db)
    headers = {**_auth(token), **INSIDE_HEADERS, **_ts_header()}

    response = await client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": "Photo", "doc_type": "EVIDENCE", "classification": "PUBLIC"},
        files={"file": ("photo.png", PNG_BYTES, "image/png")},
    )
    assert response.status_code == 201


async def test_download_returns_working_presigned_url(client, db):
    token = await _uploader_token(client, db)
    headers = {**_auth(token), **INSIDE_HEADERS, **_ts_header()}

    upload_resp = await client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": "Download Me", "doc_type": "CONTRACT", "classification": "PUBLIC"},
        files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
    )
    document_id = upload_resp.json()["document_id"]

    download_resp = await client.get(
        f"/api/v1/documents/{document_id}/download",
        headers={**_auth(token), **INSIDE_HEADERS, **_ts_header()},
    )
    assert download_resp.status_code == 200
    url = download_resp.json()["url"]

    async with httpx.AsyncClient() as raw_client:
        fetched = await raw_client.get(url)
    assert fetched.status_code == 200
    assert fetched.content == PDF_BYTES


async def test_storage_failure_leaves_no_orphan_metadata(client, db, monkeypatch):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("simulated storage outage")

    monkeypatch.setattr(storage, "put_object", _boom)

    token = await _uploader_token(client, db)
    headers = {**_auth(token), **INSIDE_HEADERS, **_ts_header()}

    response = await client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": "Should Not Persist", "doc_type": "CONTRACT", "classification": "PUBLIC"},
        files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "STORAGE_UNAVAILABLE"
    assert await db[documents_service.DOCUMENTS_COLLECTION].count_documents({}) == 0


async def test_version_no_uniqueness_enforced(db):
    document_id = ObjectId()
    await versions_service.insert_version(
        db,
        document_id=document_id,
        version_no=1,
        sha256="a" * 64,
        prev_version_hash=None,
        storage_key=f"docs/{document_id}/v1",
        size_bytes=10,
        mime="application/pdf",
        uploaded_by=ObjectId(),
    )

    with pytest.raises(DuplicateKeyError):
        await versions_service.insert_version(
            db,
            document_id=document_id,
            version_no=1,
            sha256="b" * 64,
            prev_version_hash=None,
            storage_key=f"docs/{document_id}/v1-dup",
            size_bytes=10,
            mime="application/pdf",
            uploaded_by=ObjectId(),
        )
