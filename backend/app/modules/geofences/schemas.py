"""geofences module Pydantic schemas.

GeoJSON is always [longitude, latitude] order (Guardrail #9) — this is
validated here via plausible-range checks so an accidental lat/lng swap that
puts a value outside its valid range is rejected at the API boundary.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.modules.geofences.models import MAX_POLYGON_VERTICES


def _validate_position(position: list[float]) -> list[float]:
    if len(position) != 2:
        raise ValueError("each position must be [lng, lat]")
    lng, lat = position
    if not -180 <= lng <= 180:
        raise ValueError(f"longitude out of range [-180, 180]: {lng}")
    if not -90 <= lat <= 90:
        raise ValueError(f"latitude out of range [-90, 90]: {lat}")
    return position


class GeoJSONPoint(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: list[float]

    @field_validator("coordinates")
    @classmethod
    def _validate_coordinates(cls, value: list[float]) -> list[float]:
        return _validate_position(value)


class GeoJSONPolygon(BaseModel):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[list[float]]]

    @field_validator("coordinates")
    @classmethod
    def _validate_rings(cls, rings: list[list[list[float]]]) -> list[list[list[float]]]:
        if not rings:
            raise ValueError("polygon must have at least one ring")
        for ring in rings:
            if len(ring) < 4:
                raise ValueError("each ring must have at least 4 positions (closed)")
            if len(ring) > MAX_POLYGON_VERTICES:
                raise ValueError(f"ring exceeds the {MAX_POLYGON_VERTICES}-vertex cap")
            for position in ring:
                _validate_position(position)
            if ring[0] != ring[-1]:
                raise ValueError("ring must be closed: first position must equal the last")
        return rings


class GeofenceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    region: GeoJSONPolygon
    center: GeoJSONPoint | None = None
    radius_m: float | None = Field(default=None, gt=0)


class GeofenceUpdate(BaseModel):
    """All fields optional; only provided fields are applied. There is no
    hard delete — deactivate a fence that's in use via `active: false`."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    region: GeoJSONPolygon | None = None
    center: GeoJSONPoint | None = None
    radius_m: float | None = Field(default=None, gt=0)
    active: bool | None = None


class GeofenceOut(BaseModel):
    id: str
    name: str
    region: GeoJSONPolygon
    center: GeoJSONPoint | None = None
    radius_m: float | None = None
    active: bool
    created_at: datetime


class GeofenceListOut(BaseModel):
    items: list[GeofenceOut]
    page: int
    limit: int
    total: int
