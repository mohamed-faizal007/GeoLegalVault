import pytest

from app.core.rbac import (
    APPROVE_PERFORM,
    AUDIT_VIEW,
    DOCUMENT_AMEND,
    DOCUMENT_ARCHIVE,
    DOCUMENT_SEARCH,
    DOCUMENT_UPLOAD,
    DOCUMENT_VIEW,
    GEOFENCE_MANAGE,
    REVIEW_PERFORM,
    USERS_MANAGE,
    VERIFY_PERFORM,
    RBACError,
    enforce_maker_checker,
    has_permission,
)
from app.modules.users.models import Role
from app.modules.users.schemas import UserCreate
from app.modules.users.service import create_user

# The Part 3 matrix, expressed as the exact permission set each role holds.
EXPECTED_PERMISSIONS = {
    Role.ADMINISTRATOR: {
        DOCUMENT_VIEW,
        DOCUMENT_SEARCH,
        VERIFY_PERFORM,
        USERS_MANAGE,
        GEOFENCE_MANAGE,
        AUDIT_VIEW,
        DOCUMENT_ARCHIVE,
    },
    Role.LEGAL_OFFICER: {
        DOCUMENT_UPLOAD,
        DOCUMENT_VIEW,
        DOCUMENT_SEARCH,
        DOCUMENT_AMEND,
        APPROVE_PERFORM,
        VERIFY_PERFORM,
    },
    Role.REVIEWING_OFFICER: {DOCUMENT_VIEW, DOCUMENT_SEARCH, REVIEW_PERFORM, VERIFY_PERFORM},
    Role.AUTHORIZED_STAFF: {
        DOCUMENT_UPLOAD,
        DOCUMENT_VIEW,
        DOCUMENT_SEARCH,
        DOCUMENT_AMEND,
        VERIFY_PERFORM,
    },
    Role.AUDITOR: {DOCUMENT_VIEW, DOCUMENT_SEARCH, VERIFY_PERFORM, AUDIT_VIEW},
}

ALL_PERMISSIONS = {
    DOCUMENT_UPLOAD,
    DOCUMENT_VIEW,
    DOCUMENT_SEARCH,
    DOCUMENT_AMEND,
    DOCUMENT_ARCHIVE,
    REVIEW_PERFORM,
    APPROVE_PERFORM,
    VERIFY_PERFORM,
    USERS_MANAGE,
    GEOFENCE_MANAGE,
    AUDIT_VIEW,
}


@pytest.mark.parametrize("role", list(Role))
def test_role_permission_matrix_matches_part3(role):
    expected = EXPECTED_PERMISSIONS[role]
    for permission in ALL_PERMISSIONS:
        assert has_permission(role.value, permission) == (permission in expected), (
            f"{role}:{permission} does not match the Part 3 matrix"
        )


def test_admin_cannot_upload_approve_or_review():
    for permission in (DOCUMENT_UPLOAD, APPROVE_PERFORM, REVIEW_PERFORM):
        assert has_permission(Role.ADMINISTRATOR.value, permission) is False


def test_auditor_is_read_only():
    mutating = (
        DOCUMENT_UPLOAD,
        DOCUMENT_AMEND,
        DOCUMENT_ARCHIVE,
        REVIEW_PERFORM,
        APPROVE_PERFORM,
        USERS_MANAGE,
        GEOFENCE_MANAGE,
    )
    for permission in mutating:
        assert has_permission(Role.AUDITOR.value, permission) is False


def test_unknown_permission_denied_for_every_role():
    for role in Role:
        assert has_permission(role.value, "made:up") is False


def test_unknown_role_denied():
    assert has_permission("NOT_A_REAL_ROLE", USERS_MANAGE) is False


def test_enforce_maker_checker_blocks_same_actor():
    with pytest.raises(RBACError) as exc_info:
        enforce_maker_checker("user-1", "user-1")
    assert exc_info.value.code == "MAKER_CHECKER_VIOLATION"


def test_enforce_maker_checker_allows_different_actor():
    enforce_maker_checker("uploader-1", "approver-2")  # must not raise


# --- API-level: the real /users endpoints, one request per role -----------

ROLE_PASSWORD = "Str0ngPassw0rd!"


async def _login(client, db, role: Role) -> str:
    email = f"{role.value.lower()}@example.com"
    await create_user(
        db, UserCreate(email=email, password=ROLE_PASSWORD, name=role.value, role=role)
    )
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": ROLE_PASSWORD})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("role", list(Role))
async def test_users_manage_endpoint_matches_matrix(client, db, role):
    token = await _login(client, db, role)

    response = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})

    if role == Role.ADMINISTRATOR:
        assert response.status_code == 200
    else:
        assert response.status_code == 403
        assert response.json() == {
            "error": {"code": "FORBIDDEN", "message": "Missing required permission: users:manage"}
        }
