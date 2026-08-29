"""Object storage via boto3 against an S3-compatible endpoint — Cloudflare
R2 in production, MinIO for local dev (Guardrail #4).

Bucket is private; the ONLY way bytes leave this service is a short-lived
pre-signed GET URL — the API never proxies file bytes itself. Pre-signed
URLs are signed with STORAGE_PUBLIC_ENDPOINT rather than STORAGE_ENDPOINT:
in docker-compose the backend reaches MinIO as `minio:9000`, but that
hostname means nothing to the browser/client that actually fetches the
URL, which needs `localhost:9000` instead.

Encryption at rest is a platform property, not a per-request parameter:
R2 encrypts every object transparently by default, and local MinIO has no
KMS configured (`ServerSideEncryption=AES256` on PutObject fails against a
bare MinIO with `NotImplemented: KMS not configured` — verified against the
docker-compose MinIO). So we don't pass SSE params here; asking for them
would work against neither target.
"""

import boto3
from botocore.client import BaseClient, Config

from app.core.config import get_settings

_client: BaseClient | None = None
_presign_client: BaseClient | None = None


def _build_client(endpoint_url: str) -> BaseClient:
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.STORAGE_ACCESS_KEY,
        aws_secret_access_key=settings.STORAGE_SECRET_KEY,
        region_name=settings.STORAGE_REGION,
        config=Config(signature_version="s3v4"),
    )


def get_client() -> BaseClient:
    """Client the backend itself uses to reach storage (put/get)."""
    global _client
    if _client is None:
        _client = _build_client(get_settings().STORAGE_ENDPOINT)
    return _client


def get_presign_client() -> BaseClient:
    """A separate client, pointed at STORAGE_PUBLIC_ENDPOINT, used only to
    sign pre-signed URLs — the signature is computed against whatever host
    this client is configured with, so it must be the host the *client*
    (browser, this test suite) can actually reach, not the backend's own
    (possibly container-internal) view of storage."""
    global _presign_client
    if _presign_client is None:
        _presign_client = _build_client(get_settings().STORAGE_PUBLIC_ENDPOINT)
    return _presign_client


def build_version_key(document_id: str, version_no: int) -> str:
    """Server-generated storage key — never the client's filename, which
    would allow path traversal or key collisions."""
    return f"docs/{document_id}/v{version_no}"


def put_object(data: bytes, key: str, content_type: str) -> None:
    settings = get_settings()
    get_client().put_object(
        Bucket=settings.STORAGE_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def get_object(key: str) -> bytes:
    settings = get_settings()
    response = get_client().get_object(Bucket=settings.STORAGE_BUCKET, Key=key)
    return response["Body"].read()


def generate_presigned_get(key: str, ttl: int | None = None) -> str:
    settings = get_settings()
    return get_presign_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.STORAGE_BUCKET, "Key": key},
        ExpiresIn=ttl if ttl is not None else settings.STORAGE_PRESIGN_TTL_SEC,
    )
