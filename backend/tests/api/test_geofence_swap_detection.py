"""Guardrail #9 / D-027: what a swapped [lat, lng] polygon can and cannot be
caught by. The "NOT caught" tests are deliberate: they pin the limit so nobody
reads the range check or the optional bounding box as a guarantee.

A pair [lat, lng] is read as lng' = lat, lat' = lng, so a swap is:
  * caught by the range check only if the real |longitude| > 90;
  * caught by GEOFENCE_ALLOWED_BBOX only if a transposed vertex leaves the box;
  * otherwise a perfectly valid polygon somewhere else on Earth.
"""

import pytest

from app.core.config import Settings, get_settings
from app.modules.geofences.bbox import first_position_outside, parse_bbox
from app.modules.users.models import Role
from tests.api.test_geofences import HQ_RING, _auth, _login

pytestmark = pytest.mark.asyncio(loop_scope="session")

INDIA_BBOX = "68,6,98,36"  # minLng, minLat, maxLng, maxLat


def _swap(ring: list[list[float]]) -> list[list[float]]:
    return [[lat, lng] for lng, lat in ring]


def _body(ring, **extra) -> dict:
    return {"name": "Fence", "region": {"type": "Polygon", "coordinates": [ring]}, **extra}


@pytest.fixture
def india_bbox(monkeypatch):
    monkeypatch.setattr(get_settings(), "GEOFENCE_ALLOWED_BBOX", INDIA_BBOX)


@pytest.fixture
def no_bbox(monkeypatch):
    monkeypatch.setattr(get_settings(), "GEOFENCE_ALLOWED_BBOX", "")


# ---------------------------------------------------------------- caught by range


async def test_swap_is_caught_by_range_check_when_real_longitude_exceeds_90(client, db, no_bbox):
    token = await _login(client, db, "a1@example.com", Role.ADMINISTRATOR)
    san_francisco = [
        [-122.42, 37.77],
        [-122.40, 37.77],
        [-122.40, 37.79],
        [-122.42, 37.79],
        [-122.42, 37.77],
    ]
    ok = await client.post("/api/v1/geofences", headers=_auth(token), json=_body(san_francisco))
    assert ok.status_code == 201

    swapped = await client.post(
        "/api/v1/geofences", headers=_auth(token), json=_body(_swap(san_francisco))
    )
    assert swapped.status_code == 422  # swapped "latitude" is -122.42


# ------------------------------------------------ NOT caught without a bounding box


async def test_swap_is_NOT_caught_without_a_bbox_when_real_longitude_is_within_90(
    client, db, no_bbox
):
    """The seeded demo region: 78.15°E 11.67°N swapped is 11.67°E 78.15°N (Arctic).
    Both numbers are valid, so with no bbox configured the API accepts it."""
    token = await _login(client, db, "a2@example.com", Role.ADMINISTRATOR)
    resp = await client.post("/api/v1/geofences", headers=_auth(token), json=_body(_swap(HQ_RING)))
    assert resp.status_code == 201  # accepted: this limit is documented, not fixed
    assert resp.json()["region"]["coordinates"][0][0] == [11.66, 78.14]


# ---------------------------------------------------------------- caught by the bbox


async def test_swap_is_caught_by_bbox_when_transposed_vertices_leave_the_box(
    client, db, india_bbox
):
    token = await _login(client, db, "a3@example.com", Role.ADMINISTRATOR)

    swapped = await client.post(
        "/api/v1/geofences", headers=_auth(token), json=_body(_swap(HQ_RING))
    )
    assert swapped.status_code == 422
    assert swapped.json()["error"]["code"] == "GEOFENCE_OUTSIDE_REGION"
    assert "[lng, lat]" in swapped.json()["error"]["message"]

    correct = await client.post("/api/v1/geofences", headers=_auth(token), json=_body(HQ_RING))
    assert correct.status_code == 201


async def test_bbox_is_enforced_on_update_and_on_center(client, db, india_bbox):
    token = await _login(client, db, "a4@example.com", Role.ADMINISTRATOR)
    created = await client.post("/api/v1/geofences", headers=_auth(token), json=_body(HQ_RING))
    fence_id = created.json()["id"]

    bad_region = await client.patch(
        f"/api/v1/geofences/{fence_id}",
        headers=_auth(token),
        json={"region": {"type": "Polygon", "coordinates": [_swap(HQ_RING)]}},
    )
    assert bad_region.status_code == 422
    assert bad_region.json()["error"]["code"] == "GEOFENCE_OUTSIDE_REGION"

    bad_center = await client.post(
        "/api/v1/geofences",
        headers=_auth(token),
        json=_body(HQ_RING, center={"type": "Point", "coordinates": [11.67, 78.15]}),
    )
    assert bad_center.status_code == 422

    # The rejected update changed nothing.
    still = await client.get(f"/api/v1/geofences/{fence_id}", headers=_auth(token))
    assert still.json()["region"]["coordinates"] == [HQ_RING]


async def test_one_vertex_outside_the_box_rejects_the_whole_polygon(client, db, india_bbox):
    token = await _login(client, db, "a5@example.com", Role.ADMINISTRATOR)
    ring = [[78.14, 11.66], [78.16, 11.66], [120.0, 11.68], [78.14, 11.68], [78.14, 11.66]]
    resp = await client.post("/api/v1/geofences", headers=_auth(token), json=_body(ring))
    assert resp.status_code == 422


# ------------------------------------------- NOT caught even with a bounding box


async def test_swap_is_NOT_caught_when_the_box_contains_its_own_transpose(client, db, monkeypatch):
    """A box covering [30,60]x[30,60] is symmetric under swapping, so a fence in it
    that is swapped lands back inside the box: the bbox cannot see the mistake."""
    monkeypatch.setattr(get_settings(), "GEOFENCE_ALLOWED_BBOX", "30,30,60,60")
    token = await _login(client, db, "a6@example.com", Role.ADMINISTRATOR)

    intended = [[40.0, 50.0], [40.1, 50.0], [40.1, 50.1], [40.0, 50.1], [40.0, 50.0]]
    swapped = _swap(intended)  # really 50E, 40N: a different place, still in the box
    resp = await client.post("/api/v1/geofences", headers=_auth(token), json=_body(swapped))
    assert resp.status_code == 201


async def test_swap_of_a_fence_on_the_lat_equals_lng_diagonal_is_indistinguishable(
    client, db, monkeypatch
):
    """If every vertex has lat == lng the swapped polygon is the same polygon;
    no check could (or needs to) tell the two apart."""
    monkeypatch.setattr(get_settings(), "GEOFENCE_ALLOWED_BBOX", "10,10,30,30")
    token = await _login(client, db, "a7@example.com", Role.ADMINISTRATOR)
    diagonal = [[20.0, 20.0], [22.0, 21.0], [21.0, 22.0], [20.0, 20.0]]
    assert sorted(map(tuple, _swap(diagonal))) == sorted(map(tuple, diagonal))
    resp = await client.post("/api/v1/geofences", headers=_auth(token), json=_body(diagonal))
    assert resp.status_code == 201


async def test_wrong_place_inside_the_box_is_not_a_swap_and_is_accepted(client, db, india_bbox):
    token = await _login(client, db, "a8@example.com", Role.ADMINISTRATOR)
    delhi_instead_of_chennai = [
        [77.20, 28.61],
        [77.22, 28.61],
        [77.22, 28.63],
        [77.20, 28.63],
        [77.20, 28.61],
    ]
    resp = await client.post(
        "/api/v1/geofences", headers=_auth(token), json=_body(delhi_instead_of_chennai)
    )
    assert resp.status_code == 201


# ---------------------------------------------------------------- unit: bbox + config


def test_parse_bbox_accepts_a_valid_box_and_treats_empty_as_unset():
    assert parse_bbox("") is None
    assert parse_bbox("  ") is None
    assert parse_bbox("68, 6, 98, 36") == (68.0, 6.0, 98.0, 36.0)


@pytest.mark.parametrize(
    "raw",
    [
        "68,6,98",  # wrong count
        "a,b,c,d",  # not numbers
        "98,6,68,36",  # min lng >= max lng
        "68,36,98,6",  # min lat >= max lat
        "68,6,98,95",  # latitude out of range
        "68,6,190,36",  # longitude out of range
    ],
)
def test_parse_bbox_rejects_malformed_boxes(raw):
    with pytest.raises(ValueError):
        parse_bbox(raw)


def test_malformed_bbox_fails_settings_load():
    with pytest.raises(ValueError):
        Settings(GEOFENCE_ALLOWED_BBOX="98,6,68,36")


def test_first_position_outside_reports_the_offender_and_includes_edges():
    box = (68.0, 6.0, 98.0, 36.0)
    assert first_position_outside([[68.0, 6.0], [98.0, 36.0]], box) is None
    assert first_position_outside([[78.0, 11.0], [11.0, 78.0]], box) == [11.0, 78.0]
