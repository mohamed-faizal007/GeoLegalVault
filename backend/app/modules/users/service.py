"""users module service layer — Mongo access for the users collection."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.errors import AppError
from app.core.security import hash_password
from app.modules.users.models import USERS_COLLECTION, Role
from app.modules.users.schemas import UserCreate, UserOut, UserUpdate


class EmailAlreadyExists(Exception):
    pass


class UserNotFound(Exception):
    pass


class SelfLockout(AppError):
    status_code = 409

    def __init__(self, message: str):
        super().__init__("SELF_LOCKOUT", message)


def _to_out(doc: dict[str, Any]) -> UserOut:
    return UserOut(
        id=str(doc["_id"]),
        email=doc["email"],
        name=doc["name"],
        role=doc["role"],
        assigned_geofence_ids=doc.get("assigned_geofence_ids", []),
        is_active=doc["is_active"],
        created_at=doc["created_at"],
        last_login=doc.get("last_login"),
    )


async def create_user(db: AsyncIOMotorDatabase, payload: UserCreate) -> UserOut:
    doc = {
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "name": payload.name,
        "role": payload.role.value,
        "assigned_geofence_ids": payload.assigned_geofence_ids,
        "is_active": True,
        "created_at": datetime.now(UTC),
        "last_login": None,
    }
    try:
        result = await db[USERS_COLLECTION].insert_one(doc)
    except DuplicateKeyError as exc:
        raise EmailAlreadyExists(payload.email) from exc
    doc["_id"] = result.inserted_id
    return _to_out(doc)


async def get_user_by_email(db: AsyncIOMotorDatabase, email: str) -> dict[str, Any] | None:
    return await db[USERS_COLLECTION].find_one({"email": email.lower()})


async def get_user_by_id(db: AsyncIOMotorDatabase, user_id: str) -> dict[str, Any] | None:
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        return None
    return await db[USERS_COLLECTION].find_one({"_id": oid})


async def list_users(db: AsyncIOMotorDatabase, page: int, limit: int) -> tuple[list[UserOut], int]:
    skip = (page - 1) * limit
    cursor = db[USERS_COLLECTION].find().sort("created_at", -1).skip(skip).limit(limit)
    items = [_to_out(doc) async for doc in cursor]
    total = await db[USERS_COLLECTION].count_documents({})
    return items, total


async def update_user(
    db: AsyncIOMotorDatabase,
    user_id: str,
    payload: UserUpdate,
    *,
    actor_id: ObjectId | None = None,
) -> tuple[UserOut, dict[str, Any]]:
    """Returns (user, applied_updates) so the caller can audit exactly what changed.

    An admin may not demote or deactivate their own account (D-001..D-004 in
    DECISIONS.md): with one admin that locks everyone out of user management."""
    doc = await get_user_by_id(db, user_id)
    if doc is None:
        raise UserNotFound(user_id)

    updates = payload.model_dump(exclude_unset=True)
    updates = {k: v for k, v in updates.items() if v is not None}
    if "role" in updates:
        updates["role"] = Role(updates["role"]).value

    if actor_id is not None and doc["_id"] == actor_id:
        if updates.get("role", doc["role"]) != Role.ADMINISTRATOR.value:
            raise SelfLockout("You can't remove your own administrator role")
        if updates.get("is_active") is False:
            raise SelfLockout("You can't deactivate your own account")
    if not updates:
        return _to_out(doc), {}

    await db[USERS_COLLECTION].update_one({"_id": doc["_id"]}, {"$set": updates})
    doc.update(updates)
    return _to_out(doc), updates


async def record_login(db: AsyncIOMotorDatabase, user_id: ObjectId) -> None:
    await db[USERS_COLLECTION].update_one(
        {"_id": user_id}, {"$set": {"last_login": datetime.now(UTC)}}
    )
