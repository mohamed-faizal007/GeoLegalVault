"""Deny-by-default RBAC: permission strings, the role→permission map (Plan
Part 3), the `require(permission)` dependency, and the maker≠checker helper.
"""

from app.core.deps import CurrentUser
from app.core.errors import AppError
from app.modules.users.models import Role

# --- Permission strings -----------------------------------------------------
DOCUMENT_UPLOAD = "document:upload"
DOCUMENT_VIEW = "document:view"
DOCUMENT_SEARCH = "document:search"
DOCUMENT_AMEND = "document:amend"
DOCUMENT_ARCHIVE = "document:archive"
REVIEW_PERFORM = "review:perform"
APPROVE_PERFORM = "approve:perform"
VERIFY_PERFORM = "verify:perform"
USERS_MANAGE = "users:manage"
GEOFENCE_MANAGE = "geofence:manage"
AUDIT_VIEW = "audit:view"

# --- Role -> permission map (Plan Part 3, exact) ----------------------------
# Administrator manages the system but never the document workflow itself
# (no upload/approve/review) — separation of duties keeps a super-admin from
# silently approving its own documents.
ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.ADMINISTRATOR: frozenset(
        {
            DOCUMENT_VIEW,
            DOCUMENT_SEARCH,
            VERIFY_PERFORM,
            USERS_MANAGE,
            GEOFENCE_MANAGE,
            AUDIT_VIEW,
            DOCUMENT_ARCHIVE,
        }
    ),
    Role.LEGAL_OFFICER: frozenset(
        {
            DOCUMENT_UPLOAD,
            DOCUMENT_VIEW,
            DOCUMENT_SEARCH,
            DOCUMENT_AMEND,
            APPROVE_PERFORM,
            VERIFY_PERFORM,
        }
    ),
    Role.REVIEWING_OFFICER: frozenset(
        {DOCUMENT_VIEW, DOCUMENT_SEARCH, REVIEW_PERFORM, VERIFY_PERFORM}
    ),
    Role.AUTHORIZED_STAFF: frozenset(
        {DOCUMENT_UPLOAD, DOCUMENT_VIEW, DOCUMENT_SEARCH, DOCUMENT_AMEND, VERIFY_PERFORM}
    ),
    Role.AUDITOR: frozenset({DOCUMENT_VIEW, DOCUMENT_SEARCH, VERIFY_PERFORM, AUDIT_VIEW}),
}


class RBACError(AppError):
    status_code = 403


def has_permission(role: str, permission: str) -> bool:
    try:
        role_enum = Role(role)
    except ValueError:
        return False
    return permission in ROLE_PERMISSIONS.get(role_enum, frozenset())


def require(permission: str):
    """FastAPI dependency: deny-by-default access control.

    Role is read from the freshly-loaded DB user (via get_current_user), not
    the JWT payload, so a role change or deactivation takes effect on the
    very next request rather than only after the access token expires.
    """

    def _dependency(user: CurrentUser) -> dict:
        if not has_permission(user["role"], permission):
            raise RBACError("FORBIDDEN", f"Missing required permission: {permission}")
        return user

    return _dependency


def enforce_maker_checker(uploader_id: str, actor_id: str) -> None:
    """Raise if the actor approving/reviewing a version is also its uploader."""
    if str(uploader_id) == str(actor_id):
        raise RBACError(
            "MAKER_CHECKER_VIOLATION",
            "The approver of a version must not be its uploader",
        )
