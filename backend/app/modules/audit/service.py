"""audit module service layer — the append-only security audit trail
(Plan Parts 20, 32).

`record()` is the one call site every lifecycle transition (Phase 6) and
every other security-relevant action (Phases 1-7, and this phase) uses.
Phases 1-7 called this function while it was still a no-op stub; its body
is implemented here without any of those call sites changing — they
already pass exactly the fields this collection stores.

This module exposes exactly one write path (`record`, an insert) and one
read path (`list_audit_logs`, a find). There is intentionally no
update/delete function — the append-only guarantee is enforced by this
module simply never defining one, and by the router (router.py) exposing
only GET.
"""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.db import get_database
from app.modules.audit.models import AUDIT_LOGS_COLLECTION
from app.modules.audit.schemas import AuditLogOut


async def record(
    *,
    actor_id: Any,
    action: str,
    target_type: str,
    target_id: Any,
    result: str = "SUCCESS",
    ip: str | None = None,
    location: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Append one audit record. Mongo is already a hard dependency of every
    caller here, so an insert failure surfaces like any other DB error."""
    doc: dict[str, Any] = {
        "actor_id": actor_id,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "result": result,
        "ip": ip,
        "meta": meta or {},
        "created_at": datetime.now(UTC),
    }
    if location is not None:
        # Stored only when present: a 2dsphere index treats a *missing*
        # field as "not geolocated" and skips it, but an explicit null can
        # trip index/query errors — so we simply never write the key.
        doc["location"] = location
    db = get_database()
    await db[AUDIT_LOGS_COLLECTION].insert_one(doc)


def _id_filter(value: str) -> Any:
    """actor_id/target_id are stored as whatever the caller passed —
    usually a Mongo ObjectId, sometimes a literal string ("SYSTEM" for
    system-triggered anchoring, or an email for a failed login where no
    user id exists yet). Match either representation of the same value."""
    try:
        return {"$in": [value, ObjectId(value)]}
    except InvalidId:
        return value


def to_out(doc: dict[str, Any]) -> AuditLogOut:
    return AuditLogOut(
        id=str(doc["_id"]),
        actor_id=str(doc["actor_id"]) if doc.get("actor_id") is not None else None,
        action=doc["action"],
        target_type=doc["target_type"],
        target_id=str(doc["target_id"]) if doc.get("target_id") is not None else None,
        result=doc["result"],
        ip=doc.get("ip"),
        location=doc.get("location"),
        meta=doc.get("meta") or {},
        created_at=doc["created_at"],
    )


async def list_audit_logs(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str | None = None,
    action: str | None = None,
    result: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    query: dict[str, Any] = {}
    if actor_id:
        query["actor_id"] = _id_filter(actor_id)
    if action:
        query["action"] = action
    if result:
        query["result"] = result
    if target_type:
        query["target_type"] = target_type
    if target_id:
        query["target_id"] = _id_filter(target_id)
    if date_from or date_to:
        created_range: dict[str, Any] = {}
        if date_from:
            created_range["$gte"] = date_from
        if date_to:
            created_range["$lte"] = date_to
        query["created_at"] = created_range

    skip = (page - 1) * limit
    cursor = (
        db[AUDIT_LOGS_COLLECTION].find(query).sort("created_at", -1).skip(skip).limit(limit)
    )
    items = [doc async for doc in cursor]
    total = await db[AUDIT_LOGS_COLLECTION].count_documents(query)
    return items, total
