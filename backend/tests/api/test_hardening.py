"""Phase 12 hardening: security response headers + the global rate limiter.

The rate limiter is exercised against a small standalone app (not the
shared `app` from app.main) so this test doesn't share rate-limit state
with every other test in the suite (which run with RATE_LIMIT_ENABLED=false
— see tests/conftest.py — precisely to avoid that).
"""

import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.core.rate_limit import RateLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware


@pytest.mark.asyncio(loop_scope="session")
async def test_security_headers_present(client):
    response = await client.get("/api/v1/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    # APP_ENV=development in the test env -> no HSTS (only meaningful over HTTPS).
    assert "strict-transport-security" not in response.headers


@pytest.mark.asyncio(loop_scope="session")
async def test_hsts_header_set_outside_development():
    async def _ok(_request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/ping", _ok)])
    app.add_middleware(SecurityHeadersMiddleware, hsts=True)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/ping")

    assert response.headers["strict-transport-security"] == "max-age=63072000; includeSubDomains"


@pytest.mark.asyncio(loop_scope="session")
async def test_rate_limit_blocks_after_threshold():
    async def _ok(_request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/ping", _ok)])
    app.add_middleware(RateLimitMiddleware, requests_per_min=3)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        statuses = [(await c.get("/ping")).status_code for _ in range(4)]

    assert statuses == [200, 200, 200, 429]


@pytest.mark.asyncio(loop_scope="session")
async def test_rate_limit_never_gates_health_endpoint():
    async def _health(_request):
        return JSONResponse({"status": "ok"})

    app = Starlette(routes=[Route("/api/v1/health", _health)])
    app.add_middleware(RateLimitMiddleware, requests_per_min=1)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        statuses = [(await c.get("/api/v1/health")).status_code for _ in range(5)]

    assert statuses == [200, 200, 200, 200, 200]
