"""auth module Mongo helpers — refresh-session store used for rotation and
reuse detection.

A "family" is the chain of refresh tokens descending from one login. Each
rotation inserts a new session row and marks the previous one's
`replaced_by`. If a token whose session already has `replaced_by` set is
presented again, that is a reused (already-rotated-out) token — a strong
signal of theft — so the entire family is revoked.
"""

from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

REFRESH_SESSIONS_COLLECTION = "refresh_sessions"


async def insert_session(
    db: AsyncIOMotorDatabase,
    *,
    jti: str,
    family: str,
    user_id: str,
    expires_at: datetime,
) -> None:
    await db[REFRESH_SESSIONS_COLLECTION].insert_one(
        {
            "jti": jti,
            "family": family,
            "user_id": user_id,
            "revoked": False,
            "replaced_by": None,
            "created_at": datetime.now(UTC),
            "expires_at": expires_at,
        }
    )


async def get_session(db: AsyncIOMotorDatabase, jti: str) -> dict[str, Any] | None:
    return await db[REFRESH_SESSIONS_COLLECTION].find_one({"jti": jti})


async def mark_replaced(db: AsyncIOMotorDatabase, jti: str, replaced_by: str) -> None:
    await db[REFRESH_SESSIONS_COLLECTION].update_one(
        {"jti": jti}, {"$set": {"replaced_by": replaced_by}}
    )


async def revoke_session(db: AsyncIOMotorDatabase, jti: str) -> None:
    await db[REFRESH_SESSIONS_COLLECTION].update_one({"jti": jti}, {"$set": {"revoked": True}})


async def revoke_family(db: AsyncIOMotorDatabase, family: str) -> None:
    await db[REFRESH_SESSIONS_COLLECTION].update_many(
        {"family": family}, {"$set": {"revoked": True}}
    )
