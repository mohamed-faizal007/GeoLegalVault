"""Optional deployment bounding box for geofence coordinates (Guardrail #9, D-027).

Range checks alone catch a swapped [lat, lng] pair only when the real
longitude has |lng| > 90. Inside that, a swap is a valid coordinate and is
undetectable from the numbers. A configured box (GEOFENCE_ALLOWED_BBOX, in
[minLng, minLat, maxLng, maxLat] order) turns "plausible" into "inside the
region this deployment operates in", which catches a swap whenever the
transposed vertices land outside the box. It does NOT catch a swap whose
transposed vertices are also inside the box, nor any mistake that stays inside.
"""

BBox = tuple[float, float, float, float]  # (min_lng, min_lat, max_lng, max_lat)


def parse_bbox(raw: str) -> BBox | None:
    """Parse "minLng,minLat,maxLng,maxLat". Empty string -> None (not configured)."""
    if not raw.strip():
        return None
    try:
        parts = [float(p) for p in raw.split(",")]
    except ValueError as exc:
        raise ValueError("GEOFENCE_ALLOWED_BBOX must be 4 comma-separated numbers") from exc
    if len(parts) != 4:
        raise ValueError("GEOFENCE_ALLOWED_BBOX must be minLng,minLat,maxLng,maxLat")
    min_lng, min_lat, max_lng, max_lat = parts
    if not (-180 <= min_lng < max_lng <= 180):
        raise ValueError("GEOFENCE_ALLOWED_BBOX: need -180 <= minLng < maxLng <= 180")
    if not (-90 <= min_lat < max_lat <= 90):
        raise ValueError("GEOFENCE_ALLOWED_BBOX: need -90 <= minLat < maxLat <= 90")
    return min_lng, min_lat, max_lng, max_lat


def first_position_outside(positions: list[list[float]], bbox: BBox) -> list[float] | None:
    """The first [lng, lat] position not inside the box (edges inclusive), else None."""
    min_lng, min_lat, max_lng, max_lat = bbox
    for lng, lat in positions:
        if not (min_lng <= lng <= max_lng and min_lat <= lat <= max_lat):
            return [lng, lat]
    return None
