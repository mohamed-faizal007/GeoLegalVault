"""Global per-IP request rate limiting (Plan Part 14 threat #11: "API abuse
/ brute force").

This sits alongside — not instead of — the auth module's own tighter
per-email login rate limit (app/modules/auth/service.py); this one is a
blunter, cheap backstop against a single client hammering *any* endpoint.

In-memory per-process, same trade-off already documented on the login rate
limiter: correct for the single-instance/prototype deployment target: a
multi-worker or multi-instance deployment would need a shared store (e.g.
Redis) for a real limit instead of a per-process one.
"""

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

_WINDOW_SEC = 60.0
_request_times: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, requests_per_min: int) -> None:
        super().__init__(app)
        self._limit = requests_per_min

    async def dispatch(self, request: Request, call_next):
        # /health is polled by uptime checks / load balancers — never gate it.
        if request.url.path == "/api/v1/health":
            return await call_next(request)

        ip = _client_ip(request)
        now = time.monotonic()
        recent = [t for t in _request_times[ip] if now - t < _WINDOW_SEC]
        recent.append(now)
        _request_times[ip] = recent

        if len(recent) > self._limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "too many requests — slow down and try again shortly",
                    }
                },
            )

        return await call_next(request)
