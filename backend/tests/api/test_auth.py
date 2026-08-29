import pytest

from app.modules.users.models import Role
from app.modules.users.schemas import UserCreate
from app.modules.users.service import create_user

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _make_user(
    db, email="officer@example.com", password="Str0ngPassw0rd!", role=Role.AUDITOR
):
    return await create_user(
        db, UserCreate(email=email, password=password, name="Test User", role=role)
    )


async def test_login_success_returns_access_token_and_refresh_cookie(client, db):
    await _make_user(db)

    response = await client.post(
        "/api/v1/auth/login", json={"email": "officer@example.com", "password": "Str0ngPassw0rd!"}
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert response.cookies.get("refresh_token") is not None


async def test_login_wrong_password_returns_generic_401(client, db):
    await _make_user(db)

    response = await client.post(
        "/api/v1/auth/login", json={"email": "officer@example.com", "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


async def test_login_unknown_email_returns_same_generic_401(client, db):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever123"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


async def test_protected_route_requires_token(client, db):
    await _make_user(db, role=Role.ADMINISTRATOR)

    response = await client.get("/api/v1/users")
    assert response.status_code == 401


async def test_protected_route_works_with_valid_token(client, db):
    await _make_user(db, email="admin@example.com", role=Role.ADMINISTRATOR)
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "Str0ngPassw0rd!"}
    )
    access_token = login_resp.json()["access_token"]

    response = await client.get(
        "/api/v1/users", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200


async def test_refresh_rotation_issues_new_tokens(client, db):
    await _make_user(db)
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": "officer@example.com", "password": "Str0ngPassw0rd!"}
    )
    old_refresh_cookie = login_resp.cookies.get("refresh_token")

    client.cookies.set("refresh_token", old_refresh_cookie)
    refresh_resp = await client.post("/api/v1/auth/refresh")

    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()
    new_refresh_cookie = refresh_resp.cookies.get("refresh_token")
    assert new_refresh_cookie is not None
    assert new_refresh_cookie != old_refresh_cookie


async def test_reused_refresh_token_revokes_family(client, db):
    await _make_user(db)
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": "officer@example.com", "password": "Str0ngPassw0rd!"}
    )
    old_refresh_cookie = login_resp.cookies.get("refresh_token")

    client.cookies.set("refresh_token", old_refresh_cookie)
    first_refresh = await client.post("/api/v1/auth/refresh")
    assert first_refresh.status_code == 200
    rotated_cookie = first_refresh.cookies.get("refresh_token")

    # Reuse the already-rotated-out token: must be rejected.
    client.cookies.set("refresh_token", old_refresh_cookie)
    reuse_attempt = await client.post("/api/v1/auth/refresh")
    assert reuse_attempt.status_code == 401

    # The whole family (including the token issued by the first refresh) is
    # now revoked, so it can no longer be used either.
    client.cookies.set("refresh_token", rotated_cookie)
    second_refresh = await client.post("/api/v1/auth/refresh")
    assert second_refresh.status_code == 401


async def test_refresh_without_cookie_rejected(client, db):
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
