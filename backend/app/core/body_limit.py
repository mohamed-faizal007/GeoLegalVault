"""Request-body size limit enforced before the body is read (Guardrail #5, D-028).

Pure ASGI middleware (not BaseHTTPMiddleware) so it sees the raw `receive`
stream:

1. `Content-Length` present and over the cap  -> 413 without reading anything.
2. Otherwise bytes are counted as the app pulls them; crossing the cap sends a
   413 immediately, then tells the app the client disconnected so it stops
   reading, and swallows whatever the app emits afterwards. This covers
   chunked bodies and a Content-Length that understates the real body.

The size check runs before authentication on purpose: rejecting early reveals
nothing. Per-route caps: the document upload gets MAX_UPLOAD_MB (+ multipart
framing allowance); everything else gets MAX_JSON_BODY_KB.
"""

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings

UPLOAD_PATH = "/api/v1/documents"
# Multipart boundaries and the text fields around the file part.
MULTIPART_OVERHEAD_BYTES = 1024 * 1024


def body_limit_for(method: str, path: str) -> int:
    settings = get_settings()
    if method == "POST" and path.rstrip("/") == UPLOAD_PATH:
        return settings.MAX_UPLOAD_MB * 1024 * 1024 + MULTIPART_OVERHEAD_BYTES
    return settings.MAX_JSON_BODY_KB * 1024


def _error_body(code: str, message: str) -> bytes:
    return json.dumps({"error": {"code": code, "message": message}}).encode()


async def _respond(send: Send, status: int, code: str, message: str) -> None:
    body = _error_body(code, message)
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return

        limit = body_limit_for(scope["method"], scope["path"])
        too_large = f"request body exceeds the {limit} byte limit"

        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None:
            try:
                declared_len = int(declared)
                if declared_len < 0:
                    raise ValueError
            except ValueError:
                await _respond(send, 400, "BAD_CONTENT_LENGTH", "invalid Content-Length header")
                return
            if declared_len > limit:
                await _respond(send, 413, "PAYLOAD_TOO_LARGE", too_large)
                return

        received = 0
        aborted = False

        async def counting_receive() -> Message:
            nonlocal received, aborted
            if aborted:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    aborted = True
                    await _respond(send, 413, "PAYLOAD_TOO_LARGE", too_large)
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            if not aborted:
                await send(message)

        try:
            await self.app(scope, counting_receive, guarded_send)
        except Exception:
            if not aborted:
                raise
            # The app failed because we told it the client went away; the 413
            # has already been sent, so there is nothing more to report.
