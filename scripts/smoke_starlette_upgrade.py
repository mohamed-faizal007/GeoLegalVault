"""Dev tooling: real-HTTP smoke test of the API after a framework/dependency upgrade
(first used for FastAPI 0.133 / Starlette 1.3, D-030) and of the guardrail #5
body-limit behaviour (D-028, D-033).

Sibling of scripts/test_geofence_upload.py (same X-Geo-* header pattern, so Chrome's
~150 m simulated GPS accuracy is not an issue). Talks to a running backend over plain
HTTP; imports nothing from the backend. It creates a few "Smoke test" draft documents
in whatever database the backend uses (delete them by title when done). A candidate CI
step once CI can start the stack (backend + Mongo + MinIO) with the demo seed.

Usage (repo root):
    python scripts/smoke_starlette_upgrade.py

Env overrides:
    API_BASE_URL   default http://127.0.0.1:8000/api/v1  (explicit IPv4 on purpose: a
                   docker backend may also listen on [::]:8000 with older code)
    DEMO_PASSWORD  default Demo@Pass123!  (scripts/seed.py --demo)
    MAX_UPLOAD_MB  default 10 (must match the backend)
"""

import os
import select
import socket
import sys
import time
from urllib.parse import urlparse

import httpx

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "Demo@Pass123!")
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "10"))
MIB = 1024 * 1024
UPLOAD_CAP = MAX_UPLOAD_MB * MIB + MIB  # body cap used by the middleware (+1 MiB framing)

INSIDE = {"lat": 11.67, "lng": 78.15}
ROLES = ["ADMINISTRATOR", "LEGAL_OFFICER", "REVIEWING_OFFICER", "AUTHORIZED_STAFF", "AUDITOR"]
BOUNDARY = "smokeboundary"
CRLF = bytes([13, 10])

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def email(role: str) -> str:
    return f"{role.lower()}@geolegalvault.demo"


def geo_headers(accuracy: float = 15) -> dict:
    return {
        "X-Geo-Lat": str(INSIDE["lat"]),
        "X-Geo-Lng": str(INSIDE["lng"]),
        "X-Geo-Accuracy": str(accuracy),
        "X-Geo-Timestamp": str(time.time()),
    }


def refresh_cookie_from(resp: httpx.Response) -> str | None:
    # The cookie is Secure, so a plain-HTTP cookie jar would not resend it; read the
    # Set-Cookie header and send it back by hand.
    for raw in resp.headers.get_list("set-cookie"):
        if raw.startswith("refresh_token="):
            value = raw.split(";", 1)[0].split("=", 1)[1]
            return value or None
    return None


def login(client: httpx.Client, role: str) -> tuple[str, str | None]:
    resp = client.post("/auth/login", json={"email": email(role), "password": DEMO_PASSWORD})
    if resp.status_code != 200:
        sys.exit(
            f"login as {email(role)} failed: {resp.status_code} {resp.text}\n"
            "Seed the demo users first: python scripts/seed.py --demo"
        )
    return resp.json()["access_token"], refresh_cookie_from(resp)


def multipart(file_bytes: bytes, filename: str = "smoke.txt") -> tuple[bytes, str]:
    parts = []
    for name, value in (("title", "Smoke test"), ("doc_type", "CONTRACT"), ("classification", "PUBLIC")):
        parts.append(
            f'--{BOUNDARY}'.encode() + CRLF
            + f'Content-Disposition: form-data; name="{name}"'.encode() + CRLF + CRLF
            + value.encode() + CRLF
        )
    parts.append(
        f"--{BOUNDARY}".encode() + CRLF
        + f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode() + CRLF
        + b"Content-Type: text/plain" + CRLF + CRLF
        + file_bytes + CRLF
    )
    parts.append(f"--{BOUNDARY}--".encode() + CRLF)
    return b"".join(parts), f"multipart/form-data; boundary={BOUNDARY}"


def raw_post(path: str, headers: dict, chunks, *, chunked: bool, content_length: int | None = None,
             stop_after: int | None = None, timeout: float = 30) -> dict:
    """POST over a bare socket so we can see WHEN the server answers relative to how much
    body we had sent. Stops sending as soon as a response is readable."""
    parsed = urlparse(API_BASE_URL)
    sock = socket.create_connection((parsed.hostname, parsed.port or 80), timeout=timeout)
    head = [f"POST {parsed.path}{path} HTTP/1.1", f"Host: {parsed.hostname}:{parsed.port}"]
    for k, v in headers.items():
        head.append(f"{k}: {v}")
    if chunked:
        head.append("Transfer-Encoding: chunked")
    elif content_length is not None:
        head.append(f"Content-Length: {content_length}")
    sock.sendall(("\r\n".join(head) + "\r\n\r\n").encode())

    sent = 0
    answered_at = None
    started = time.monotonic()
    send_error = None
    try:
        for chunk in chunks:
            readable, _, _ = select.select([sock], [], [], 0)
            if readable:
                answered_at = sent
                break
            payload = (f"{len(chunk):x}".encode() + CRLF + chunk + CRLF) if chunked else chunk
            sock.sendall(payload)
            sent += len(chunk)
            if stop_after is not None and sent >= stop_after:
                break
        else:
            if chunked:
                sock.sendall(b"0" + CRLF + CRLF)
    except OSError as exc:  # server closed on us mid-send
        send_error = type(exc).__name__
    data = b""
    sock.settimeout(5)
    try:
        while b"\r\n\r\n" not in data:
            piece = sock.recv(65536)
            if not piece:
                break
            data += piece
        # read a little of the body too
        sock.settimeout(1)
        try:
            data += sock.recv(65536)
        except OSError:
            pass
    except OSError as exc:
        send_error = send_error or type(exc).__name__
    sock.close()
    status = None
    if data.startswith(b"HTTP/"):
        status = int(data.split(b" ", 2)[1])
    body = data.split(b"\r\n\r\n", 1)[1].decode(errors="replace") if b"\r\n\r\n" in data else ""
    return {
        "status": status, "body": body, "sent": sent, "answered_at": answered_at,
        "send_error": send_error, "seconds": round(time.monotonic() - started, 2),
    }


def blocks(total: int, size: int = 64 * 1024):
    left = total
    while left > 0:
        n = min(size, left)
        left -= n
        yield b"a" * n


def responsive(client: httpx.Client, token: str) -> tuple[bool, str]:
    t0 = time.monotonic()
    h = client.get("/health")
    d = client.get("/documents", params={"limit": 1}, headers={"Authorization": f"Bearer {token}"})
    dt = time.monotonic() - t0
    return (h.status_code == 200 and d.status_code == 200 and dt < 3,
            f"/health {h.status_code}, /documents {d.status_code}, {dt:.2f}s")


def main() -> None:
    client = httpx.Client(base_url=API_BASE_URL, timeout=30)

    print("[0] Which backend am I talking to? (new code answers an oversize Content-Length with 413 PAYLOAD_TOO_LARGE)")
    probe = raw_post("/documents", {"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"},
                     iter(()), chunked=False, content_length=50 * MIB)
    is_new = probe["status"] == 413 and "PAYLOAD_TOO_LARGE" in probe["body"]
    record("backend has the body-limit middleware", is_new, f"{probe['status']} {probe['body'][:90]!r}")
    if not is_new:
        sys.exit("This is not the new code (docker image built earlier?). Aborting.")

    print("\n[1] Login -> refresh (cookie) -> logout -> reuse of old refresh tokens")
    resp = client.post("/auth/login", json={"email": email("LEGAL_OFFICER"), "password": DEMO_PASSWORD})
    rt1 = refresh_cookie_from(resp)
    record("login", resp.status_code == 200 and rt1 is not None, f"{resp.status_code}, refresh cookie set={rt1 is not None}")
    r2 = client.post("/auth/refresh", headers={"Cookie": f"refresh_token={rt1}"})
    rt2 = refresh_cookie_from(r2)
    record("refresh with cookie", r2.status_code == 200 and rt2 not in (None, rt1),
           f"{r2.status_code}, new access token={'access_token' in r2.json() if r2.status_code == 200 else False}, cookie rotated={rt2 not in (None, rt1)}")
    lo = client.post(  # logout needs the bearer token as well as the cookie
        "/auth/logout",
        headers={"Cookie": f"refresh_token={rt2}", "Authorization": f"Bearer {r2.json()['access_token']}"},
    )
    record("logout", lo.status_code == 204, str(lo.status_code))
    reuse_after_logout = client.post("/auth/refresh", headers={"Cookie": f"refresh_token={rt2}"})
    record("reuse refresh token after logout is rejected", reuse_after_logout.status_code == 401,
           str(reuse_after_logout.status_code))
    reuse_rotated = client.post("/auth/refresh", headers={"Cookie": f"refresh_token={rt1}"})
    record("reuse of the rotated-out (original) refresh token is rejected", reuse_rotated.status_code == 401,
           str(reuse_rotated.status_code))

    token, _ = login(client, "LEGAL_OFFICER")
    auth = {"Authorization": f"Bearer {token}"}

    print("\n[2] Upload inside the geofence (accuracy 15 m) and byte-exact download")
    content = (b"GeoLegalVault starlette-upgrade smoke test. " * 40) + str(time.time()).encode()
    up = client.post("/documents", headers={**auth, **geo_headers()},
                     data={"title": "Smoke test", "doc_type": "CONTRACT", "classification": "PUBLIC"},
                     files={"file": ("smoke.txt", content, "text/plain")})
    record("upload inside fence", up.status_code == 201, f"{up.status_code} {up.text[:80]}")
    if up.status_code == 201:
        doc_id = up.json()["document_id"]
        dl = client.get(f"/documents/{doc_id}/download", headers={**auth, **geo_headers()})
        record("download returns a pre-signed URL", dl.status_code == 200 and "url" in dl.json(), str(dl.status_code))
        if dl.status_code == 200:
            fetched = httpx.get(dl.json()["url"], timeout=30)
            record("downloaded bytes are identical to the uploaded bytes",
                   fetched.status_code == 200 and fetched.content == content,
                   f"{fetched.status_code}, {len(fetched.content)} bytes vs {len(content)} sent")

    print(f"\n[3] Oversized AUTHENTICATED uploads (limit {MAX_UPLOAD_MB} MiB)")
    body, ctype = multipart(b"a" * (MAX_UPLOAD_MB * MIB + 1))
    over = client.post("/documents", headers={**auth, **geo_headers(), "Content-Type": ctype}, content=body)
    code = over.json().get("error", {}).get("code") if over.headers.get("content-type", "").startswith("application/json") else None
    record("file 1 byte over the limit", over.status_code == 413 and code == "FILE_TOO_LARGE", f"{over.status_code} {code}")
    ok, detail = responsive(client, token)
    record("backend responsive afterwards", ok, detail)
    body, ctype = multipart(b"a" * (MAX_UPLOAD_MB * MIB + 5 * MIB))
    # Over the cap with an honest Content-Length: the server answers 413 straight away and
    # closes, so a normal HTTP client would die with a connection reset while still sending
    # (that is the point of rejecting early). Use the raw socket to read the answer.
    r = raw_post("/documents", {**auth, **geo_headers(), "Content-Type": ctype},
                 (body[i:i + 65536] for i in range(0, len(body), 65536)), chunked=False,
                 content_length=len(body))
    record("body far over the cap (Content-Length known): client can read 413 PAYLOAD_TOO_LARGE",
           r["status"] == 413 and "PAYLOAD_TOO_LARGE" in r["body"],
           f"{r['status']}, body bytes pushed before the answer was seen={r['sent']} of {len(body)} "
           f"(socket buffers), send error: {r['send_error']}")
    ok, detail = responsive(client, token)
    record("backend responsive afterwards", ok, detail)

    print("\n[4] Oversized UNAUTHENTICATED uploads")
    r = raw_post("/documents", {"Content-Type": ctype}, iter(()), chunked=False, content_length=50 * MIB)
    record("declared 50 MiB, no credentials: rejected before any body is sent",
           r["status"] == 413 and r["sent"] == 0, f"{r['status']}, body bytes sent={r['sent']}, {r['seconds']}s")
    size = 5 * MIB
    r = raw_post("/documents", {"Content-Type": ctype}, blocks(size), chunked=False, content_length=size)
    record("honest 5 MiB (under the cap), no credentials: 401",
           r["status"] == 401,
           f"{r['status']}; server answered after we had sent {r['answered_at'] if r['answered_at'] is not None else 'all ' + str(r['sent'])} "
           f"of {size} bytes (send error: {r['send_error']}) -- socket buffering makes this indicative, not proof; "
           "the ASGI test counts bytes the app actually pulled (0)")
    ok, detail = responsive(client, token)
    record("backend responsive afterwards", ok, detail)

    print("\n[5] Chunked uploads (no Content-Length)")
    small_body, ctype = multipart(b"chunked smoke test file\n" * 50)
    r = raw_post("/documents", {**auth, **geo_headers(), "Content-Type": ctype},
                 (small_body[i:i + 4096] for i in range(0, len(small_body), 4096)), chunked=True)
    record("small valid multipart sent chunked, authenticated: 201", r["status"] == 201, f"{r['status']} {r['body'][:70]!r}")
    big_body, ctype = multipart(b"a" * (MAX_UPLOAD_MB * MIB + 5 * MIB))
    r = raw_post("/documents", {**auth, **geo_headers(), "Content-Type": ctype},
                 (big_body[i:i + 65536] for i in range(0, len(big_body), 65536)), chunked=True)
    record("oversized chunked, authenticated: 413 and the sender is cut off at about the cap",
           r["status"] == 413 and (r["sent"] < len(big_body)),
           f"{r['status']}, sent {r['sent']} of {len(big_body)} bytes (cap {UPLOAD_CAP}), send error: {r['send_error']}")
    r = raw_post("/documents", {"Content-Type": ctype}, blocks(30 * MIB), chunked=True)
    record("chunked, no credentials: rejected without reading the stream",
           r["status"] in (401, 413) and r["sent"] < 30 * MIB,
           f"{r['status']}, sent {r['sent']} of {30 * MIB} bytes, send error: {r['send_error']}")
    ok, detail = responsive(client, token)
    record("backend responsive afterwards", ok, detail)

    print("\n[6] Health and one request per role")
    h = client.get("/health")
    record("GET /health", h.status_code == 200 and h.json().get("status") == "ok", f"{h.status_code} {h.json()}")
    for role in ROLES:
        tok, _ = login(client, role)
        a = {"Authorization": f"Bearer {tok}"}
        docs = client.get("/documents", params={"limit": 1}, headers=a)
        if role == "ADMINISTRATOR":
            extra_path, extra_expect = "/users", 200
        elif role == "AUDITOR":
            extra_path, extra_expect = "/audit", 200
        else:
            extra_path, extra_expect = "/users", 403
        extra = client.get(extra_path, headers=a)
        record(f"{role}", docs.status_code == 200 and extra.status_code == extra_expect,
               f"GET /documents {docs.status_code}; GET {extra_path} {extra.status_code} (expected {extra_expect})")

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED:", "; ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
