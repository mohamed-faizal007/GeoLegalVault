"""users module service layer — Mongo access for the users collection."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.security import hash_password
from app.modules.users.models import USERS_COLLECTION, Role
from app.modules.users.schemas import UserCreate, UserOut, UserUpdate


class EmailAlreadyExists(Exception):
    pass


class UserNotFound(Exception):
    pass


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


async def update_user(db: AsyncIOMotorDatabase, user_id: str, payload: UserUpdate) -> UserOut:
    doc = await get_user_by_id(db, user_id)
    if doc is None:
        raise UserNotFound(user_id)

    updates = payload.model_dump(exclude_unset=True)
    if "role" in updates and updates["role"] is not None:
        updates["role"] = Role(updates["role"]).value
    if not updates:
        return _to_out(doc)

    await db[USERS_COLLECTION].update_one({"_id": doc["_id"]}, {"$set": updates})
    doc.update(updates)
    return _to_out(doc)


async def record_login(db: AsyncIOMotorDatabase, user_id: ObjectId) -> None:
    await db[USERS_COLLECTION].update_one(
        {"_id": user_id}, {"$set": {"last_login": datetime.now(UTC)}}
    )


async def create_admin(
    db: AsyncIOMotorDatabase, email: str, password: str, name: str = "Administrator"
) -> UserOut:
    """Used by scripts/seed.py to provision the first admin account."""
    existing = await get_user_by_email(db, email)
    if existing is not None:
        raise EmailAlreadyExists(email)
    return await create_user(
        db,
        UserCreate(email=email, password=password, name=name, role=Role.ADMINISTRATOR),
    )
