"""The authz matrix Phase 11 asks for: every representative endpoint × every
role, parametrized, asserting allow/deny matches core.rbac.has_permission
exactly. test_rbac.py already proves the permission *map* matches Part 3
and drives one endpoint (/users) end-to-end; this file extends that same
proof across the other read endpoints that need no per-request setup
(document/version-scoped write actions already have their own dedicated
maker-checker/workflow/geofence tests elsewhere).
"""

import pytest

from app.core.rbac import AUDIT_VIEW, DOCUMENT_VIEW, GEOFENCE_MANAGE, USERS_MANAGE, has_permission
from app.modules.users.models import Role
from app.modules.users.schemas import UserCreate
from app.modules.users.service import create_user

pytestmark = pytest.mark.asyncio(loop_scope="session")

PASSWORD = "Str0ngPassw0rd!"

# (method, path, permission required by that endpoint) — all GETs that work
# with no path params and no pre-existing data, so the only variable under
# test is the RBAC decision itself.
ENDPOINTS = [
    ("GET", "/api/v1/documents", DOCUMENT_VIEW),
    ("GET", "/api/v1/geofences", GEOFENCE_MANAGE),
    ("GET", "/api/v1/users", USERS_MANAGE),
    ("GET", "/api/v1/audit", AUDIT_VIEW),
    ("GET", "/api/v1/reports/summary", AUDIT_VIEW),
]


async def _login(client, db, role: Role) -> str:
    email = f"matrix-{role.value.lower()}@example.com"
    await create_user(db, UserCreate(email=email, password=PASSWORD, name=role.value, role=role))
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.parametrize("role", list(Role))
async def test_authz_matrix_every_endpoint_matches_permission_map(client, db, role):
    token = await _login(client, db, role)
    headers = {"Authorization": f"Bearer {token}"}

    for method, path, permission in ENDPOINTS:
        response = await client.request(method, path, headers=headers)
        expected_allowed = has_permission(role.value, permission)

        if expected_allowed:
            assert response.status_code == 200, (
                f"{role.value} x {method} {path}: expected 200 (has {permission}), "
                f"got {response.status_code}: {response.text}"
            )
        else:
            assert response.status_code == 403, (
                f"{role.value} x {method} {path}: expected 403 (lacks {permission}), "
                f"got {response.status_code}: {response.text}"
            )
            assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_unauthenticated_requests_get_401_not_403(client, db):
    """Deny-by-default starts with authentication, not authorization — a
    request with no token at all must fail as 401, distinctly from a
    logged-in-but-unpermitted 403."""
    for method, path, _permission in ENDPOINTS:
        response = await client.request(method, path)
        assert response.status_code == 401, (
            f"{method} {path}: expected 401, got {response.status_code}"
        )
