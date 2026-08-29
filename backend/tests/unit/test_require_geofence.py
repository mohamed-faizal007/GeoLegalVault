"""HTTP-level tests for the require_geofence() dependency itself: it must be
reusable behind any endpoint (mounted here on a throwaway FastAPI app, the
way Phase 4+ will mount it on upload/download/approve/amend) and it must
never trust anything the client asserts about its own location — only the
server-side DB query decides.
"""

import time
from typing import Annotated

import httpx
import pytest
from fastapi import Depends, FastAPI

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import register_exception_handlers
from app.modules.geofences.schemas import GeofenceCreate, GeoJSONPolygon
from app.modules.geofences.service import create_geofence
from app.services.geofence import require_geofence

pytestmark = pytest.mark.asyncio(loop_scope="session")

HQ_RING = [
    [78.14, 11.66],
    [78.16, 11.66],
    [78.16, 11.68],
    [78.14, 11.68],
    [78.14, 11.66],
]
INSIDE = {"lat": 11.67, "lng": 78.15}
OUTSIDE = {"lat": 11.00, "lng": 77.00}


def _build_test_app(user: dict, db) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    _require_geofence = require_geofence("test_operation")

    @app.post("/guarded")
    async def guarded(fence: Annotated[dict, Depends(_require_geofence)]) -> dict:
        return {"fence_id": str(fence["_id"])}

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return app


def _client_for(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def _fence_and_app(db):
    fence = await create_geofence(
        db, GeofenceCreate(name="HQ", region=GeoJSONPolygon(coordinates=[HQ_RING]))
    )
    user = {"assigned_geofence_ids": [fence.id]}
    return fence, _build_test_app(user, db)


async def test_allows_inside_denies_outside(db):
    fence, app = await _fence_and_app(db)

    async with _client_for(app) as client:
        inside_resp = await client.post(
            "/guarded",
            json={
                "lat": INSIDE["lat"],
                "lng": INSIDE["lng"],
                "accuracy": 10,
                "timestamp": time.time(),
            },
        )
        assert inside_resp.status_code == 200
        assert inside_resp.json() == {"fence_id": fence.id}

        outside_resp = await client.post(
            "/guarded",
            json={
                "lat": OUTSIDE["lat"],
                "lng": OUTSIDE["lng"],
                "accuracy": 10,
                "timestamp": time.time(),
            },
        )
        assert outside_resp.status_code == 403
        assert outside_resp.json()["error"]["code"] == "GEOFENCE_DENIED"


async def test_client_supplied_allow_flag_is_ignored(db):
    """The dependency must never trust a client-asserted allow/deny flag."""
    _fence, app = await _fence_and_app(db)

    async with _client_for(app) as client:
        response = await client.post(
            "/guarded",
            json={
                "lat": OUTSIDE["lat"],
                "lng": OUTSIDE["lng"],
                "accuracy": 10,
                "timestamp": time.time(),
                "allowed": True,  # attacker-controlled; must have no effect
            },
        )
        assert response.status_code == 403


async def test_low_accuracy_rejected(db):
    _fence, app = await _fence_and_app(db)

    async with _client_for(app) as client:
        response = await client.post(
            "/guarded",
            json={
                "lat": INSIDE["lat"],
                "lng": INSIDE["lng"],
                "accuracy": 500,
                "timestamp": time.time(),
            },
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "LOCATION_LOW_CONFIDENCE"


async def test_stale_timestamp_rejected(db):
    _fence, app = await _fence_and_app(db)

    async with _client_for(app) as client:
        response = await client.post(
            "/guarded",
            json={
                "lat": INSIDE["lat"],
                "lng": INSIDE["lng"],
                "accuracy": 10,
                "timestamp": time.time() - 3600,
            },
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "LOCATION_STALE"


async def test_location_via_headers_also_works(db):
    fence, app = await _fence_and_app(db)

    async with _client_for(app) as client:
        response = await client.post(
            "/guarded",
            headers={
                "X-Geo-Lat": str(INSIDE["lat"]),
                "X-Geo-Lng": str(INSIDE["lng"]),
                "X-Geo-Accuracy": "10",
                "X-Geo-Timestamp": str(time.time()),
            },
        )
        assert response.status_code == 200
        assert response.json() == {"fence_id": fence.id}
