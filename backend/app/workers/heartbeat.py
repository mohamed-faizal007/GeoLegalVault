"""The anchor worker's heartbeat (REL-01, D-040).

One document in the app's own database, not a new service (Guardrail #10). It records
*that* the loop is alive and the *code* of the last error, never an error message
(which could embed an RPC URL with a key, Guardrail #2).
"""

from datetime import UTC, datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.services.anchor_errors import classify_anchor_error

HEARTBEATS_COLLECTION = "worker_heartbeats"
ANCHOR_WORKER_ID = "anchor_worker"


async def beat(db: AsyncIOMotorDatabase, *, error: BaseException | None = None) -> None:
    """Called once per worker loop. A clean loop stamps `last_ok_at`; a failed one stamps
    `last_error_at` and the error's fixed code. The last error stays visible after a
    clean loop, so an operator can see what went wrong and when."""
    moment = datetime.now(UTC)
    fields: dict = {"last_beat_at": moment}
    if error is None:
        fields["last_ok_at"] = moment
    else:
        fields["last_error_at"] = moment
        fields["last_error_code"] = classify_anchor_error(error)
    await db[HEARTBEATS_COLLECTION].update_one(
        {"_id": ANCHOR_WORKER_ID},
        {"$set": fields, "$inc": {"passes": 1}},
        upsert=True,
    )


async def is_fresh(db: AsyncIOMotorDatabase) -> bool:
    """True if the worker has beaten within ANCHOR_WORKER_STALE_SEC. Never having run is
    not fresh."""
    row = await db[HEARTBEATS_COLLECTION].find_one({"_id": ANCHOR_WORKER_ID})
    if row is None or row.get("last_beat_at") is None:
        return False
    last = row["last_beat_at"]
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return datetime.now(UTC) - last <= timedelta(seconds=get_settings().ANCHOR_WORKER_STALE_SEC)
