"""Server-side geofence enforcement (Plan Part 11).

This is the ONLY place inside/outside is decided. Guardrails #5 and #6:
the check is always server-side, and it's a policy/defense-in-depth
control, not a security guarantee — browser GPS is spoofable (DevTools
sensors, fake-GPS apps, payload tampering before it reaches the server).
"""

import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import CurrentUser
from app.core.errors import AppError
from app.modules.audit import service as audit
from app.modules.geofences.models import GEOFENCES_COLLECTION

_logger = logging.getLogger(__name__)


class LocationInput(BaseModel):
    lat: float
    lng: float
    accuracy: float = Field(ge=0)
    timestamp: float  # Unix epoch seconds, UTC

    @field_validator("lat")
    @classmethod
    def _lat_range(cls, value: float) -> float:
        if not -90 <= value <= 90:
            raise ValueError("lat must be between -90 and 90")
        return value

    @field_validator("lng")
    @classmethod
    def _lng_range(cls, value: float) -> float:
        if not -180 <= value <= 180:
            raise ValueError("lng must be between -180 and 180")
        return value


class InvalidLocation(AppError):
    status_code = 422

    def __init__(self, message: str):
        super().__init__("INVALID_LOCATION", message)


class LocationLowConfidence(AppError):
    status_code = 422

    def __init__(self, message: str):
        super().__init__("LOCATION_LOW_CONFIDENCE", message)


class LocationStale(AppError):
    status_code = 422

    def __init__(self, message: str):
        super().__init__("LOCATION_STALE", message)


class GeofenceDenied(AppError):
    status_code = 403

    def __init__(self, message: str):
        super().__init__("GEOFENCE_DENIED", message)


async def check_location(
    db: AsyncIOMotorDatabase,
    user: dict[str, Any],
    lat: float,
    lng: float,
    accuracy_m: float,
    client_ts: float,
    *,
    ip: str | None = None,
) -> dict[str, Any]:
    """Fail-closed on poor accuracy or a stale reading, then run the real
    point-in-polygon query. Never trust a client-supplied allow/deny flag."""
    settings = get_settings()
    point = {"type": "Point", "coordinates": [lng, lat]}

    if accuracy_m > settings.GEO_ACCURACY_MAX_M:
        _logger.warning(
            "geofence: LOCATION_LOW_CONFIDENCE",
            extra={"user_id": str(user.get("_id")), "accuracy_m": accuracy_m, "ip": ip},
        )
        raise LocationLowConfidence(
            f"location accuracy {accuracy_m:.0f}m exceeds the "
            f"{settings.GEO_ACCURACY_MAX_M}m maximum"
        )

    now = datetime.now(UTC).timestamp()
    age_sec = now - client_ts
    if age_sec > settings.GEO_FRESHNESS_MAX_SEC:
        _logger.warning(
            "geofence: LOCATION_STALE",
            extra={"user_id": str(user.get("_id")), "age_sec": age_sec, "ip": ip},
        )
        raise LocationStale(
            f"location is {age_sec:.0f}s old (max {settings.GEO_FRESHNESS_MAX_SEC}s)"
        )

    object_ids = []
    for fence_id in user.get("assigned_geofence_ids", []):
        try:
            object_ids.append(ObjectId(fence_id))
        except InvalidId:
            continue

    fence = None
    if object_ids:
        fence = await db[GEOFENCES_COLLECTION].find_one(
            {
                "_id": {"$in": object_ids},
                "active": True,
                "region": {"$geoIntersects": {"$geometry": point}},
            }
        )

    if fence is None:
        actor_id = user.get("_id")
        _logger.warning(
            "geofence: GEOFENCE_DENIED",
            extra={"user_id": str(actor_id), "lat": lat, "lng": lng, "ip": ip},
        )
        await audit.record(
            actor_id=actor_id,
            action="GEOFENCE_DENIED",
            target_type="user",
            target_id=actor_id,
            result="DENIED",
            ip=ip,
            location=point,
            meta={"accuracy_m": accuracy_m},
        )
        raise GeofenceDenied("current location is outside all geofences assigned to this user")
    return fence


_HEADER_NAMES = {
    "lat": "x-geo-lat",
    "lng": "x-geo-lng",
    "accuracy": "x-geo-accuracy",
    "timestamp": "x-geo-timestamp",
}


async def _extract_location_payload(request: Request) -> dict[str, Any]:
    """Read {lat,lng,accuracy,timestamp} from X-Geo-* headers if present,
    otherwise from the request body (JSON or form) — whichever shape the
    guarded endpoint already uses (multipart upload vs JSON approve/amend)."""
    if all(name in request.headers for name in _HEADER_NAMES.values()):
        return {key: request.headers[name] for key, name in _HEADER_NAMES.items()}

    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        return {key: form.get(key) for key in _HEADER_NAMES}
    if "application/json" in content_type:
        body = await request.json()
        return {key: body.get(key) for key in _HEADER_NAMES}

    raise InvalidLocation("Missing location data: expected lat/lng/accuracy/timestamp")


def require_geofence(context: str = "sensitive_operation"):
    """FastAPI dependency guarding upload/download/approve/amend (later
    phases). Extracts the client's claimed location, then delegates the
    actual inside/outside decision to check_location() — this dependency
    never itself decides allow/deny from anything the client asserts.
    """

    async def _dependency(
        request: Request,
        user: CurrentUser,
        db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    ) -> dict[str, Any]:
        raw = await _extract_location_payload(request)
        try:
            location = LocationInput.model_validate(raw)
        except ValidationError as exc:
            raise InvalidLocation(f"invalid location data for {context}: {exc}") from exc

        ip = request.client.host if request.client else None
        return await check_location(
            db,
            user,
            location.lat,
            location.lng,
            location.accuracy,
            location.timestamp,
            ip=ip,
        )

    return _dependency
