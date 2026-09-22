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


async def test_update_geofence_name_and_region_records_audit(client, db):
    token = await _login(client, db, "admin-update@example.com", Role.ADMINISTRATOR)

    create_resp = await client.post(
        "/api/v1/geofences",
        headers=_auth(token),
        json={"name": "HQ Campus", "region": {"type": "Polygon", "coordinates": [HQ_RING]}},
    )
    geofence_id = create_resp.json()["id"]

    new_ring = [
        [78.20, 11.70],
        [78.22, 11.70],
        [78.22, 11.72],
        [78.20, 11.72],
        [78.20, 11.70],
    ]
    update_resp = await client.patch(
        f"/api/v1/geofences/{geofence_id}",
        headers=_auth(token),
        json={"name": "HQ Campus (relocated)", "region": {"type": "Polygon", "coordinates": [new_ring]}},
    )
    assert update_resp.status_code == 200
    body = update_resp.json()
    assert body["name"] == "HQ Campus (relocated)"
    assert body["region"]["coordinates"] == [new_ring]

    entry = await db["audit_logs"].find_one({"action": "GEOFENCE_UPDATE"})
    assert entry is not None
    assert sorted(entry["meta"]["fields"]) == ["name", "region"]
    assert entry["meta"]["name"] == "HQ Campus (relocated)"
    # Raw polygon coordinates never land in the audit trail.
    assert "coordinates" not in str(entry["meta"])


async def test_no_op_update_does_not_record_audit(client, db):
    token = await _login(client, db, "admin-noop@example.com", Role.ADMINISTRATOR)

    create_resp = await client.post(
        "/api/v1/geofences",
        headers=_auth(token),
        json={"name": "NoOp", "region": {"type": "Polygon", "coordinates": [HQ_RING]}},
    )
    geofence_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/api/v1/geofences/{geofence_id}", headers=_auth(token), json={}
    )
    assert update_resp.status_code == 200

    entry = await db["audit_logs"].find_one({"action": "GEOFENCE_UPDATE"})
    assert entry is None


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
