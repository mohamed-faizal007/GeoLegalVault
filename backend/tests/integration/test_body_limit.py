"""Guardrail #5 / D-028: the size limit is enforced before the body is read,
and authentication runs before a multipart upload body is parsed.

The oversize/streaming tests drive the ASGI app directly with a hand-written
`receive` so we can see exactly how many body bytes the server pulled. Real
HTTP servers already stop at Content-Length bytes, so a Content-Length that
understates the body is mostly an ASGI-layer concern; chunked and
length-less bodies are the realistic path.
"""

import asyncio
import hashlib
from collections.abc import AsyncIterator

import pytest

from app.core.body_limit import MULTIPART_OVERHEAD_BYTES, body_limit_for
from app.core.config import get_settings
from app.main import app
from tests.integration.test_upload import (
    INSIDE_HEADERS,
    _auth,
    _ts_header,
    _uploader_token,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")

MAX_FILE = get_settings().MAX_UPLOAD_MB * 1024 * 1024
UPLOAD_LIMIT = body_limit_for("POST", "/api/v1/documents")
CHUNK = 64 * 1024
BOUNDARY = "testboundary"
MULTIPART = f"multipart/form-data; boundary={BOUNDARY}"


class AsgiResult:
    def __init__(self) -> None:
        self.status: int | None = None
        self.body = b""
        self.consumed = 0  # request-body bytes the app pulled via receive()


async def _asgi_post(
    path: str,
    headers: dict[str, str],
    chunks: AsyncIterator[bytes],
    content_length: int | None = None,
) -> AsgiResult:
    result = AsgiResult()
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    if content_length is not None:
        raw_headers.append((b"content-length", str(content_length).encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": raw_headers,
        "client": ("203.0.113.9", 4321),
        "server": ("test", 80),
    }
    iterator = chunks.__aiter__()

    async def receive():
        try:
            chunk = await iterator.__anext__()
        except StopAsyncIteration:
            return {"type": "http.request", "body": b"", "more_body": False}
        result.consumed += len(chunk)
        return {"type": "http.request", "body": chunk, "more_body": True}

    async def send(message):
        if message["type"] == "http.response.start":
            result.status = message["status"]
        elif message["type"] == "http.response.body":
            result.body += message.get("body", b"")

    await asyncio.wait_for(app(scope, receive, send), timeout=30)
    return result


async def _blocks(total: int | None, chunk: int = CHUNK) -> AsyncIterator[bytes]:
    """`total` bytes in `chunk`-sized pieces; None = never stops."""
    sent = 0
    while total is None or sent < total:
        size = chunk if total is None else min(chunk, total - sent)
        sent += size
        yield b"x" * size


async def _multipart_stream(file_total: int | None) -> AsyncIterator[bytes]:
    """A well-formed multipart body whose file part is `file_total` bytes (None = endless)."""
    head, _ = _multipart(b"")
    # Everything before the closing delimiter, ending inside the file part.
    closing = bytes([13, 10]) + b"--" + BOUNDARY.encode() + b"--" + bytes([13, 10])
    yield head[: head.index(closing)]
    async for block in _blocks(file_total):
        yield block


def _text_filler(size: int) -> bytes:
    """`size` bytes of genuine ASCII text lines, so libmagic reports text/plain on any
    version (a single repeated byte is sniffed differently by different libmagic builds, D-035)."""
    line = b"GeoLegalVault size-limit filler line\n"
    return (line * (size // len(line) + 1))[:size]


def _multipart(file_bytes: bytes, content_type: str = "text/plain") -> tuple[bytes, str]:
    parts = []
    for name, value in (
        ("title", "Big"),
        ("doc_type", "CONTRACT"),
        ("classification", "PUBLIC"),
    ):
        disposition = f'Content-Disposition: form-data; name="{name}"'
        parts.append(f"--{BOUNDARY}\r\n{disposition}\r\n\r\n{value}\r\n".encode())
    file_disposition = 'Content-Disposition: form-data; name="file"; filename="big.txt"'
    parts.append(
        f"--{BOUNDARY}\r\n{file_disposition}\r\nContent-Type: {content_type}\r\n\r\n".encode()
        + file_bytes
        + b"\r\n"
    )
    parts.append(f"--{BOUNDARY}--\r\n".encode())
    return b"".join(parts), MULTIPART


async def test_oversized_unauthenticated_upload_rejected_by_content_length_without_reading(client):
    declared = UPLOAD_LIMIT + 1
    result = await _asgi_post(
        "/api/v1/documents",
        {"content-type": MULTIPART},
        _blocks(declared),
        content_length=declared,
    )
    assert result.status == 413
    assert b"PAYLOAD_TOO_LARGE" in result.body
    assert result.consumed == 0


async def test_in_limit_unauthenticated_upload_is_rejected_before_the_body_is_read(client):
    """The size is fine, so the cap does not apply — but with no credentials the
    multipart body must never be pulled (auth runs before the body is parsed)."""
    size = 5 * 1024 * 1024
    result = await _asgi_post(
        "/api/v1/documents",
        {"content-type": MULTIPART},
        _blocks(size),
        content_length=size,
    )
    assert result.status == 401
    assert result.consumed == 0


async def test_unauthenticated_streaming_upload_is_never_read_at_all(client):
    """Chunked / lying-length bodies from a caller with no credentials: auth fails
    first, so not one body byte is pulled (stronger than aborting at the cap)."""
    for chunks, declared in ((_blocks(None), None), (_blocks(UPLOAD_LIMIT * 3), 100)):
        result = await _asgi_post(
            "/api/v1/documents", {"content-type": MULTIPART}, chunks, content_length=declared
        )
        assert result.status == 401
        assert result.consumed == 0


async def test_lying_content_length_is_caught_while_streaming(client, db):
    token = await _uploader_token(client, db)
    headers = {**_auth(token), **INSIDE_HEADERS, **_ts_header(), "content-type": MULTIPART}
    result = await _asgi_post(
        "/api/v1/documents",
        headers,
        _multipart_stream(UPLOAD_LIMIT * 3),
        content_length=100,  # claims 100 bytes, sends three times the limit
    )
    assert result.status == 413
    assert b"PAYLOAD_TOO_LARGE" in result.body
    assert UPLOAD_LIMIT < result.consumed <= UPLOAD_LIMIT + CHUNK
    assert await db["documents"].count_documents({}) == 0


async def test_chunked_body_without_content_length_is_aborted_at_the_limit(client, db):
    token = await _uploader_token(client, db)
    headers = {**_auth(token), **INSIDE_HEADERS, **_ts_header(), "content-type": MULTIPART}
    # An endless stream: the request only terminates if the server aborts.
    result = await _asgi_post("/api/v1/documents", headers, _multipart_stream(None))
    assert result.status == 413
    assert UPLOAD_LIMIT < result.consumed <= UPLOAD_LIMIT + CHUNK
    assert await db["documents"].count_documents({}) == 0
    assert await db["document_versions"].count_documents({}) == 0


async def test_non_upload_routes_get_the_small_json_cap(client):
    json_limit = get_settings().MAX_JSON_BODY_KB * 1024
    result = await _asgi_post(
        "/api/v1/auth/login", {"content-type": "application/json"}, _blocks(None)
    )
    assert result.status == 413
    assert json_limit < result.consumed <= json_limit + CHUNK

    declared = json_limit + 1
    by_header = await _asgi_post(
        "/api/v1/auth/login",
        {"content-type": "application/json"},
        _blocks(declared),
        content_length=declared,
    )
    assert by_header.status == 413
    assert by_header.consumed == 0


async def test_malformed_content_length_is_a_400(client):
    result = await _asgi_post(
        "/api/v1/documents",
        {"content-type": MULTIPART, "content-length": "abc"},
        _blocks(10),
    )
    assert result.status == 400


async def test_upload_exactly_at_the_file_size_limit_still_works(client, db):
    token = await _uploader_token(client, db)
    data = _text_filler(MAX_FILE)
    body, content_type = _multipart(data)
    assert len(body) <= UPLOAD_LIMIT  # framing fits inside the allowance
    assert len(body) - MAX_FILE < MULTIPART_OVERHEAD_BYTES

    resp = await client.post(
        "/api/v1/documents",
        headers={**_auth(token), **INSIDE_HEADERS, **_ts_header(), "content-type": content_type},
        content=body,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["sha256"] == hashlib.sha256(data).hexdigest()


async def test_file_one_byte_over_the_limit_gets_file_too_large_not_a_cap_error(client, db):
    token = await _uploader_token(client, db)
    body, content_type = _multipart(_text_filler(MAX_FILE + 1))
    assert len(body) <= UPLOAD_LIMIT  # passes the byte cap; the file-size rule decides

    resp = await client.post(
        "/api/v1/documents",
        headers={**_auth(token), **INSIDE_HEADERS, **_ts_header(), "content-type": content_type},
        content=body,
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"
