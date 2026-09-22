"""geofences module router — Admin-only CRUD (deactivate, never hard-delete)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.db import get_db
from app.core.rbac import GEOFENCE_MANAGE, require
from app.modules.audit import service as audit
from app.modules.geofences import service
from app.modules.geofences.schemas import (
    GeofenceCreate,
    GeofenceListOut,
    GeofenceOut,
    GeofenceUpdate,
)

router = APIRouter(prefix="/geofences", tags=["geofences"])

_require_geofence_manage = require(GEOFENCE_MANAGE)


@router.post("", response_model=GeofenceOut, status_code=status.HTTP_201_CREATED)
async def create_geofence(
    payload: GeofenceCreate,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    actor: Annotated[dict, Depends(_require_geofence_manage)],
) -> GeofenceOut:
    created = await service.create_geofence(db, payload)
    await audit.record(
        actor_id=actor["_id"],
        action="GEOFENCE_CREATE",
        target_type="geofence",
        target_id=created.id,
        result="SUCCESS",
        meta={"name": created.name},
    )
    return created


@router.get("", response_model=GeofenceListOut)
async def list_geofences(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _actor: Annotated[dict, Depends(_require_geofence_manage)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> GeofenceListOut:
    items, total = await service.list_geofences(db, page, limit)
    return GeofenceListOut(items=items, page=page, limit=limit, total=total)


@router.get("/{geofence_id}", response_model=GeofenceOut)
async def get_geofence(
    geofence_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _actor: Annotated[dict, Depends(_require_geofence_manage)],
) -> GeofenceOut:
    doc = await service.get_geofence_by_id(db, geofence_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Geofence not found")
    return service.to_out(doc)


@router.patch("/{geofence_id}", response_model=GeofenceOut)
async def update_geofence(
    geofence_id: str,
    payload: GeofenceUpdate,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    actor: Annotated[dict, Depends(_require_geofence_manage)],
) -> GeofenceOut:
    try:
        updated = await service.update_geofence(db, geofence_id, payload)
    except service.GeofenceNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Geofence not found") from exc

    applied = payload.model_dump(exclude_unset=True)
    if applied:
        # Field names always; the name value too (small, not PII). Never the
        # raw region/center coordinates — bulky and not useful in a listing.
        meta: dict = {"fields": sorted(applied)}
        if "name" in applied:
            meta["name"] = applied["name"]
        if "active" in applied:
            meta["active"] = applied["active"]
        await audit.record(
            actor_id=actor["_id"],
            action="GEOFENCE_UPDATE",
            target_type="geofence",
            target_id=geofence_id,
            result="SUCCESS",
            meta=meta,
        )
    return updated
