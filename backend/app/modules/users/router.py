"""users module router — Admin-provisioned user management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.db import get_db
from app.core.rbac import USERS_MANAGE, require
from app.modules.audit import service as audit
from app.modules.users import service
from app.modules.users.schemas import UserCreate, UserListOut, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

_require_users_manage = require(USERS_MANAGE)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    actor: Annotated[dict, Depends(_require_users_manage)],
) -> UserOut:
    try:
        created = await service.create_user(db, payload)
    except service.EmailAlreadyExists as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered") from exc

    await audit.record(
        actor_id=actor["_id"],
        action="USER_CREATE",
        target_type="user",
        target_id=created.id,
        result="SUCCESS",
        meta={"email": created.email, "role": created.role},
    )
    return created


@router.get("", response_model=UserListOut)
async def list_users(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _actor: Annotated[dict, Depends(_require_users_manage)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> UserListOut:
    items, total = await service.list_users(db, page, limit)
    return UserListOut(items=items, page=page, limit=limit, total=total)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _actor: Annotated[dict, Depends(_require_users_manage)],
) -> UserOut:
    try:
        return await service.update_user(db, user_id, payload)
    except service.UserNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found") from exc
