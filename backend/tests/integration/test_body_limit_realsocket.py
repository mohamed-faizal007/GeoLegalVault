"""Guardrail #5 / D-033: over a REAL TCP connection to a real uvicorn server, an
oversized upload is rejected AND the client can read the rejection.

The ASGI-level tests (test_body_limit.py) prove the app stops reading, but they
cannot see transport behaviour. This file exists because D-028 originally sent
`Connection: close` with the 413: uvicorn then closed the socket with request
bytes still unread, the OS reset the connection, and a real client got a network
error instead of the 413 (found by scripts/smoke_starlette_upgrade.py).

A uvicorn subprocess is started on a free local port against the same test
database as the in-process fixtures.
"""

import os
import select
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from app.core.body_limit import body_limit_for
from app.core.config import get_settings
from tests.integration.test_upload import INSIDE_HEADERS, _auth, _ts_header, _uploader_token

pytestmark = pytest.mark.asyncio(loop_scope="session")

CRLF = bytes([13, 10])
MIB = 1024 * 1024
MAX_FILE = get_settings().MAX_UPLOAD_MB * MIB
UPLOAD_LIMIT = body_limit_for("POST", "/api/v1/documents")
BOUNDARY = "realsocketboundary"
MULTIPART = f"multipart/form-data; boundary={BOUNDARY}"
BACKEND_DIR = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server():
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port),
         "--log-level", "warning"],
        cwd=BACKEND_DIR,
        env=os.environ.copy(),  # conftest already pointed MONGODB_DB at the test database
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            pytest.fail("uvicorn subprocess exited during startup")
        try:
            if httpx.get(f"{base}/openapi.json", timeout=2).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.3)
    else:
        proc.kill()
        pytest.fail("uvicorn subprocess did not become ready")
    yield {"port": port, "base": base}
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def multipart_prefix() -> bytes:
    """Well-formed multipart body up to (and including) the start of the file part."""
    parts = b""
    for name, value in (("title", "Big"), ("doc_type", "CONTRACT"), ("classification", "PUBLIC")):
        parts += (
            f"--{BOUNDARY}".encode() + CRLF
            + f'Content-Disposition: form-data; name="{name}"'.encode() + CRLF + CRLF
            + value.encode() + CRLF
        )
    parts += (
        f"--{BOUNDARY}".encode() + CRLF
        + b'Content-Disposition: form-data; name="file"; filename="big.txt"' + CRLF
        + b"Content-Type: text/plain" + CRLF + CRLF
    )
    return parts


def body_stream(total: int, chunk: int = 64 * 1024):
    prefix = multipart_prefix()
    yield prefix
    left = total - len(prefix)
    while left > 0:
        n = min(chunk, left)
        left -= n
        yield b"a" * n


def post(port: int, headers: dict, chunks, *, chunked: bool, content_length: int | None = None,
         deadline_sec: float = 30) -> dict:
    """POST over a bare socket. Sends until the server answers (or we run out of body),
    then reads the answer. status is None if the client could not read a response, which
    is exactly the defect this file guards against."""
    sock = socket.create_connection(("127.0.0.1", port), timeout=deadline_sec)
    head = ["POST /api/v1/documents HTTP/1.1", f"Host: 127.0.0.1:{port}"]
    head += [f"{k}: {v}" for k, v in headers.items()]
    if chunked:
        head.append("Transfer-Encoding: chunked")
    elif content_length is not None:
        head.append(f"Content-Length: {content_length}")
    sock.sendall(("\r\n".join(head) + "\r\n\r\n").encode())

    sent = 0
    send_error = None
    start = time.monotonic()
    try:
        for chunk in chunks:
            if select.select([sock], [], [], 0)[0]:
                break
            if time.monotonic() - start > deadline_sec:
                break
            sock.sendall((f"{len(chunk):x}".encode() + CRLF + chunk + CRLF) if chunked else chunk)
            sent += len(chunk)
    except OSError as exc:
        send_error = type(exc).__name__
    data = b""
    sock.settimeout(5)
    try:
        while b"\r\n\r\n" not in data:
            piece = sock.recv(65536)
            if not piece:
                break
            data += piece
        sock.settimeout(1)
        try:
            data += sock.recv(65536)
        except OSError:
            pass
    except OSError as exc:
        send_error = send_error or type(exc).__name__
    sock.close()
    status = int(data.split(b" ", 2)[1]) if data.startswith(b"HTTP/") else None
    text = data.split(b"\r\n\r\n", 1)[1].decode(errors="replace") if b"\r\n\r\n" in data else ""
    return {"status": status, "body": text, "sent": sent, "send_error": send_error}


async def _auth_headers(client, db) -> dict:
    token = await _uploader_token(client, db)
    return {**_auth(token), **INSIDE_HEADERS, **_ts_header()}


async def test_oversized_authenticated_upload_with_honest_content_length_gets_a_readable_413(
    client, db, server
):
    headers = {**await _auth_headers(client, db), "Content-Type": MULTIPART}
    total = UPLOAD_LIMIT + 4 * MIB
    result = post(server["port"], headers, body_stream(total), chunked=False, content_length=total)
    assert result["status"] == 413, result
    assert "PAYLOAD_TOO_LARGE" in result["body"]
    assert result["sent"] < total  # the server did not make us send it all


async def test_file_just_over_the_limit_gets_a_readable_file_too_large(client, db, server):
    headers = {**await _auth_headers(client, db), "Content-Type": MULTIPART}
    total = len(multipart_prefix()) + MAX_FILE + 1 + 64  # under the byte cap, over the file rule
    assert total < UPLOAD_LIMIT

    def stream():
        yield multipart_prefix()
        left = MAX_FILE + 1
        while left > 0:
            n = min(64 * 1024, left)
            left -= n
            yield b"a" * n
        yield CRLF + f"--{BOUNDARY}--".encode() + CRLF

    exact = len(multipart_prefix()) + MAX_FILE + 1 + len(CRLF + f"--{BOUNDARY}--".encode() + CRLF)
    result = post(server["port"], headers, stream(), chunked=False, content_length=exact)
    assert result["status"] == 413, result
    assert "FILE_TOO_LARGE" in result["body"]


async def test_oversized_chunked_authenticated_upload_gets_a_readable_413(client, db, server):
    headers = {**await _auth_headers(client, db), "Content-Type": MULTIPART}
    result = post(server["port"], headers, body_stream(UPLOAD_LIMIT + 4 * MIB), chunked=True)
    assert result["status"] == 413, result
    assert "PAYLOAD_TOO_LARGE" in result["body"]
    assert result["sent"] < UPLOAD_LIMIT + 4 * MIB


async def test_oversized_unauthenticated_upload_gets_a_readable_413(server):
    total = UPLOAD_LIMIT + 4 * MIB
    result = post(
        server["port"], {"Content-Type": MULTIPART}, body_stream(total), chunked=False,
        content_length=total,
    )
    assert result["status"] == 413, result
    assert "PAYLOAD_TOO_LARGE" in result["body"]


async def test_oversized_unauthenticated_chunked_upload_is_answered_without_being_read(server):
    """No credentials: authentication fails before the body is parsed, so the answer is a
    readable 401 (not a reset) and the client is cut off long before sending it all."""
    total = UPLOAD_LIMIT + 4 * MIB
    result = post(server["port"], {"Content-Type": MULTIPART}, body_stream(total), chunked=True)
    assert result["status"] in (401, 413), result
    assert result["sent"] < total


async def test_other_requests_stay_prompt_while_a_half_sent_upload_hangs(client, db, server):
    headers = {**await _auth_headers(client, db), "Content-Type": MULTIPART}
    port = server["port"]
    hanging = socket.create_connection(("127.0.0.1", port), timeout=10)
    declared = 5 * MIB  # within the cap, so the app keeps waiting for the rest
    head = ["POST /api/v1/documents HTTP/1.1", f"Host: 127.0.0.1:{port}"]
    head.append(f"Content-Length: {declared}")
    head += [f"{k}: {v}" for k, v in headers.items()]
    hanging.sendall(("\r\n".join(head) + "\r\n\r\n").encode() + multipart_prefix() + b"a" * 100_000)
    try:
        started = time.monotonic()
        health = httpx.get(f"{server['base']}/api/v1/health", timeout=10)
        login = httpx.post(
            f"{server['base']}/api/v1/auth/login",
            json={"email": "uploader@example.com", "password": "Str0ngPassw0rd!"},
            timeout=10,
        )
        elapsed = time.monotonic() - started
        assert health.status_code == 200
        assert login.status_code == 200
        assert elapsed < 5, f"other requests took {elapsed:.1f}s while an upload was left hanging"
    finally:
        hanging.close()
