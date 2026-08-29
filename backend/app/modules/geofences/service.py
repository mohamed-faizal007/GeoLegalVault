"""geofences module service layer — Mongo access for the geofences collection."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.modules.geofences.models import GEOFENCES_COLLECTION
from app.modules.geofences.schemas import GeofenceCreate, GeofenceOut, GeofenceUpdate


class GeofenceNotFound(Exception):
    pass


def to_out(doc: dict[str, Any]) -> GeofenceOut:
    return GeofenceOut(
        id=str(doc["_id"]),
        name=doc["name"],
        region=doc["region"],
        center=doc.get("center"),
        radius_m=doc.get("radius_m"),
        active=doc["active"],
        created_at=doc["created_at"],
    )


async def create_geofence(db: AsyncIOMotorDatabase, payload: GeofenceCreate) -> GeofenceOut:
    doc = {
        "name": payload.name,
        "region": payload.region.model_dump(),
        "center": payload.center.model_dump() if payload.center else None,
        "radius_m": payload.radius_m,
        "active": True,
        "created_at": datetime.now(UTC),
    }
    result = await db[GEOFENCES_COLLECTION].insert_one(doc)
    doc["_id"] = result.inserted_id
    return to_out(doc)


async def get_geofence_by_id(db: AsyncIOMotorDatabase, geofence_id: str) -> dict[str, Any] | None:
    try:
        oid = ObjectId(geofence_id)
    except InvalidId:
        return None
    return await db[GEOFENCES_COLLECTION].find_one({"_id": oid})


async def list_geofences(
    db: AsyncIOMotorDatabase, page: int, limit: int
) -> tuple[list[GeofenceOut], int]:
    skip = (page - 1) * limit
    cursor = db[GEOFENCES_COLLECTION].find().sort("created_at", -1).skip(skip).limit(limit)
    items = [to_out(doc) async for doc in cursor]
    total = await db[GEOFENCES_COLLECTION].count_documents({})
    return items, total


async def update_geofence(
    db: AsyncIOMotorDatabase, geofence_id: str, payload: GeofenceUpdate
) -> GeofenceOut:
    doc = await get_geofence_by_id(db, geofence_id)
    if doc is None:
        raise GeofenceNotFound(geofence_id)

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return to_out(doc)

    await db[GEOFENCES_COLLECTION].update_one({"_id": doc["_id"]}, {"$set": updates})
    doc.update(updates)
    return to_out(doc)
