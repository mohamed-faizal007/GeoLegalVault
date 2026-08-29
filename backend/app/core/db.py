"""Async MongoDB access via Motor.

Index creation is centralized in ensure_indexes() so each later phase can
append its own collection's indexes here without touching connection setup.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import get_settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=2000)
    return _client


def get_database() -> AsyncIOMotorDatabase:
    settings = get_settings()
    return get_client()[settings.MONGODB_DB]


async def get_db() -> AsyncIOMotorDatabase:
    """FastAPI dependency yielding the app's database handle."""
    return get_database()


async def ping_mongo() -> bool:
    try:
        await get_client().admin.command("ping")
        return True
    except Exception:
        return False


async def ensure_indexes() -> None:
    """Create/verify indexes on startup. Extended in later phases as more
    collections are introduced."""
    db = get_database()
    await db["users"].create_index("email", unique=True)
    await db["refresh_sessions"].create_index("jti", unique=True)
    await db["refresh_sessions"].create_index("family")
    await db["geofences"].create_index([("region", "2dsphere")])
    await db["geofences"].create_index([("center", "2dsphere")])

    await db["documents"].create_index("status")
    await db["documents"].create_index("owner_id")
    await db["documents"].create_index([("status", 1), ("doc_type", 1)])
    await db["documents"].create_index([("title", "text"), ("tags", "text")])

    await db["document_versions"].create_index(
        [("document_id", 1), ("version_no", 1)], unique=True
    )
    await db["document_versions"].create_index("sha256")

    # sparse: a FAILED anchor attempt (RPC never reachable) has tx_hash=null,
    # and multiple such rows must not collide on the unique index.
    await db["blockchain_anchors"].create_index("tx_hash", unique=True, sparse=True)
    await db["blockchain_anchors"].create_index("version_id")


async def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
