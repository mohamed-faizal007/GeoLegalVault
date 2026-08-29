"""Tests for server-side geofence enforcement (check_location).

These run against a real Mongo (the `db` fixture from conftest.py targets a
dedicated test database) because the check is a real $geoIntersects query —
there is no meaningful way to unit-test point-in-polygon logic without one.
"""

import time

import pytest
from bson import ObjectId

from app.modules.geofences.models import GEOFENCES_COLLECTION
from app.modules.geofences.schemas import GeofenceCreate, GeoJSONPolygon
from app.modules.geofences.service import create_geofence
from app.services.geofence import (
    GeofenceDenied,
    LocationInput,
    LocationLowConfidence,
    LocationStale,
    check_location,
)

_async_test = pytest.mark.asyncio(loop_scope="session")

# A small square: lng in [78.14, 78.16], lat in [11.66, 11.68] (Plan Part 10's
# own HQ campus example).
HQ_RING = [
    [78.14, 11.66],
    [78.16, 11.66],
    [78.16, 11.68],
    [78.14, 11.68],
    [78.14, 11.66],
]

INSIDE = {"lat": 11.67, "lng": 78.15}
OUTSIDE = {"lat": 11.00, "lng": 77.00}
ON_VERTEX = {"lat": 11.66, "lng": 78.14}  # a corner of the polygon


def _user(fence_ids: list[str]) -> dict:
    return {"assigned_geofence_ids": fence_ids}


async def _make_fence(db, *, active: bool = True) -> str:
    fence = await create_geofence(
        db, GeofenceCreate(name="HQ Test Fence", region=GeoJSONPolygon(coordinates=[HQ_RING]))
    )
    if not active:
        await db[GEOFENCES_COLLECTION].update_one(
            {"_id": ObjectId(fence.id)}, {"$set": {"active": False}}
        )
    return fence.id


@_async_test
async def test_point_inside_geofence_passes(db):
    fence_id = await _make_fence(db)
    result = await check_location(
        db, _user([fence_id]), INSIDE["lat"], INSIDE["lng"], accuracy_m=10, client_ts=time.time()
    )
    assert str(result["_id"]) == fence_id


@_async_test
async def test_point_outside_geofence_denied(db):
    fence_id = await _make_fence(db)
    with pytest.raises(GeofenceDenied):
        await check_location(
            db,
            _user([fence_id]),
            OUTSIDE["lat"],
            OUTSIDE["lng"],
            accuracy_m=10,
            client_ts=time.time(),
        )


@_async_test
async def test_point_on_edge_is_deterministic(db):
    # A polygon vertex is an exact, unambiguous boundary point (unlike a
    # naively-interpolated edge midpoint, which 2dsphere's geodesic edges can
    # place just outside the polygon due to spherical vs. planar geometry —
    # confirmed empirically, not assumed). $geoIntersects treats the
    # boundary as part of the polygon, so this must match every time.
    fence_id = await _make_fence(db)
    for _ in range(3):
        result = await check_location(
            db,
            _user([fence_id]),
            ON_VERTEX["lat"],
            ON_VERTEX["lng"],
            accuracy_m=10,
            client_ts=time.time(),
        )
        assert str(result["_id"]) == fence_id


@_async_test
async def test_accuracy_over_threshold_is_low_confidence():
    with pytest.raises(LocationLowConfidence):
        await check_location(
            None, _user(["irrelevant"]), INSIDE["lat"], INSIDE["lng"], 500, time.time()
        )


@_async_test
async def test_stale_timestamp_rejected():
    old_ts = time.time() - 3600  # 1 hour old, well past GEO_FRESHNESS_MAX_SEC
    with pytest.raises(LocationStale):
        await check_location(None, _user(["irrelevant"]), INSIDE["lat"], INSIDE["lng"], 10, old_ts)


@_async_test
async def test_inactive_geofence_does_not_match(db):
    fence_id = await _make_fence(db, active=False)
    with pytest.raises(GeofenceDenied):
        await check_location(
            db,
            _user([fence_id]),
            INSIDE["lat"],
            INSIDE["lng"],
            accuracy_m=10,
            client_ts=time.time(),
        )


@_async_test
async def test_user_not_assigned_to_any_fence_denied(db):
    await _make_fence(db)
    with pytest.raises(GeofenceDenied):
        await check_location(
            db, _user([]), INSIDE["lat"], INSIDE["lng"], accuracy_m=10, client_ts=time.time()
        )


def test_swapped_lat_lng_rejected_by_range_validation():
    # A real point near Manila (lat=14.60, lng=120.98) swapped becomes
    # lat=120.98 — outside the valid latitude range [-90, 90] — caught
    # immediately, before any DB query runs. (The HQ example's own
    # coordinates happen to swap into another in-range pair, so range
    # validation alone can't catch every swap — only ones like this.)
    with pytest.raises(ValueError):
        LocationInput(lat=120.98, lng=14.60, accuracy=10, timestamp=time.time())
