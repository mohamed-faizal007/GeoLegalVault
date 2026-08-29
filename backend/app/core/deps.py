"""Shared FastAPI dependencies: current-user extraction.

Permission enforcement (deny-by-default RBAC) lives in `core/rbac.py`'s
`require(permission)` dependency, which builds on `get_current_user` below.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.db import get_db
from app.core.security import TokenError, TokenType, verify_token
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
