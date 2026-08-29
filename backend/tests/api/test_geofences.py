import pytest

from app.modules.users.models import Role
from app.modules.users.schemas import UserCreate
from app.modules.users.service import create_user

pytestmark = pytest.mark.asyncio(loop_scope="session")

HQ_RING = [
    [78.14, 11.66],
    [78.16, 11.66],
    [78.16, 11.68],
    [78.14, 11.68],
    [78.14, 11.66],
]


async def _login(client, db, email: str, role: Role) -> str:
    await create_user(
        db, UserCreate(email=email, password="Str0ngPassw0rd!", name="Test", role=role)
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Str0ngPassw0rd!"}
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_admin_can_create_list_get_and_deactivate_geofence(client, db):
    token = await _login(client, db, "admin@example.com", Role.ADMINISTRATOR)

    create_resp = await client.post(
        "/api/v1/geofences",
        headers=_auth(token),
        json={"name": "HQ Campus", "region": {"type": "Polygon", "coordinates": [HQ_RING]}},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["active"] is True
    geofence_id = body["id"]

    list_resp = await client.get("/api/v1/geofences", headers=_auth(token))
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    get_resp = await client.get(f"/api/v1/geofences/{geofence_id}", headers=_auth(token))
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "HQ Campus"

    deactivate_resp = await client.patch(
        f"/api/v1/geofences/{geofence_id}", headers=_auth(token), json={"active": False}
    )
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["active"] is False

    # Deactivating is not deleting: it's still readable.
    still_there = await client.get(f"/api/v1/geofences/{geofence_id}", headers=_auth(token))
    assert still_there.status_code == 200


async def test_non_admin_cannot_manage_geofences(client, db):
    token = await _login(client, db, "staff@example.com", Role.AUTHORIZED_STAFF)

    response = await client.post(
        "/api/v1/geofences",
        headers=_auth(token),
        json={"name": "X", "region": {"type": "Polygon", "coordinates": [HQ_RING]}},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_unclosed_ring_rejected(client, db):
    token = await _login(client, db, "admin2@example.com", Role.ADMINISTRATOR)

    unclosed_ring = HQ_RING[:-1]  # drop the closing position
    response = await client.post(
        "/api/v1/geofences",
        headers=_auth(token),
        json={"name": "Bad", "region": {"type": "Polygon", "coordinates": [unclosed_ring]}},
    )
    assert response.status_code == 422


async def test_swapped_lat_lng_rejected(client, db):
    token = await _login(client, db, "admin3@example.com", Role.ADMINISTRATOR)

    # A real polygon near Manila (lng~121, lat~14) with lng/lat swapped in
    # each position: the resulting "latitude" (~121) is out of [-90, 90].
    swapped_ring = [
        [14.60, 120.98],
        [14.60, 120.99],
        [14.61, 120.99],
        [14.61, 120.98],
        [14.60, 120.98],
    ]
    response = await client.post(
        "/api/v1/geofences",
        headers=_auth(token),
        json={"name": "Swapped", "region": {"type": "Polygon", "coordinates": [swapped_ring]}},
    )
    assert response.status_code == 422


async def test_too_many_vertices_rejected(client, db):
    token = await _login(client, db, "admin4@example.com", Role.ADMINISTRATOR)

    ring = [[0.0 + i * 0.001, 0.0] for i in range(101)]
    ring.append(ring[0])
    response = await client.post(
        "/api/v1/geofences",
        headers=_auth(token),
        json={"name": "TooBig", "region": {"type": "Polygon", "coordinates": [ring]}},
    )
    assert response.status_code == 422


async def test_geofence_not_found_returns_404(client, db):
    token = await _login(client, db, "admin5@example.com", Role.ADMINISTRATOR)

    response = await client.get(
        "/api/v1/geofences/000000000000000000000000", headers=_auth(token)
    )
    assert response.status_code == 404
