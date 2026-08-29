"""Shared FastAPI dependencies: current-user extraction and a minimal role
guard. Phase 2 replaces the role guard with the full permission-string RBAC
dependency (`require(permission)`); this stays deliberately small until then.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.db import get_db
from app.core.security import TokenError, TokenType, verify_token
from app.modules.users.models import Role
from app.modules.users.service import get_user_by_id

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
) -> dict:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        decoded = verify_token(credentials.credentials, expected_type=TokenType.ACCESS)
    except TokenError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc

    user = await get_user_by_id(db, decoded.sub)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    if not user.get("is_active", False):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    return user


CurrentUser = Annotated[dict, Depends(get_current_user)]


def require_role(*allowed: Role):
    """Minimal role gate for Phase 1 (Admin-only user-management endpoints).

    Role is read from the freshly-loaded DB user (via get_current_user), not
    blindly trusted from the JWT payload, per the threat-model requirement
    that sensitive ops re-derive role server-side.
    """

    def _dependency(user: CurrentUser) -> dict:
        if user["role"] not in {role.value for role in allowed}:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return _dependency
