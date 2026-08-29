import pytest

from app.modules.auth.service import login
from app.modules.users.models import Role
from app.modules.users.schemas import UserCreate
from app.modules.users.service import create_user

pytestmark = pytest.mark.asyncio(loop_scope="session")

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "Str0ngPassw0rd!"


async def _admin_token(client, db) -> str:
    await create_user(
        db,
        UserCreate(
            email=ADMIN_EMAIL, password=ADMIN_PASSWORD, name="Admin", role=Role.ADMINISTRATOR
        ),
    )
    _user, access_token, _refresh = await login(db, ADMIN_EMAIL, ADMIN_PASSWORD)
    return access_token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_admin_can_create_list_and_deactivate_user(client, db):
    token = await _admin_token(client, db)

    create_resp = await client.post(
        "/api/v1/users",
        headers=_auth(token),
        json={
            "email": "staff@example.com",
            "password": "AnotherStr0ngPass!",
            "name": "Staff Member",
            "role": "AUTHORIZED_STAFF",
        },
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["email"] == "staff@example.com"
    assert "password_hash" not in body
    assert body["is_active"] is True
    user_id = body["id"]

    list_resp = await client.get("/api/v1/users", headers=_auth(token))
    assert list_resp.status_code == 200
    listed = list_resp.json()
    assert listed["total"] >= 2  # admin + staff
    assert all("password_hash" not in item for item in listed["items"])

    deactivate_resp = await client.patch(
        f"/api/v1/users/{user_id}", headers=_auth(token), json={"is_active": False}
    )
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["is_active"] is False


async def test_duplicate_email_rejected(client, db):
    token = await _admin_token(client, db)

    payload = {
        "email": "dupe@example.com",
        "password": "Str0ngPassw0rd!",
        "name": "First",
        "role": "AUTHORIZED_STAFF",
    }
    first = await client.post("/api/v1/users", headers=_auth(token), json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/users", headers=_auth(token), json=payload)
    assert second.status_code == 409


async def test_non_admin_cannot_manage_users(client, db):
    await create_user(
        db,
        UserCreate(
            email="auditor@example.com",
            password="Str0ngPassw0rd!",
            name="Auditor",
            role=Role.AUDITOR,
        ),
    )
    _user, access_token, _refresh = await login(db, "auditor@example.com", "Str0ngPassw0rd!")

    response = await client.get("/api/v1/users", headers=_auth(access_token))
    assert response.status_code == 403


async def test_deactivated_user_cannot_authenticate_protected_route(client, db):
    token = await _admin_token(client, db)
    create_resp = await client.post(
        "/api/v1/users",
        headers=_auth(token),
        json={
            "email": "temp@example.com",
            "password": "Str0ngPassw0rd!",
            "name": "Temp",
            "role": "AUTHORIZED_STAFF",
        },
    )
    user_id = create_resp.json()["id"]

    _user, temp_token, _refresh = await login(db, "temp@example.com", "Str0ngPassw0rd!")

    await client.patch(f"/api/v1/users/{user_id}", headers=_auth(token), json={"is_active": False})

    response = await client.get("/api/v1/users", headers=_auth(temp_token))
    assert response.status_code == 403
