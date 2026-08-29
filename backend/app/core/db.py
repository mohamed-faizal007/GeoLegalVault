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
    """Create/verify indexes on startup. Extended in later phases as
    collections (users, documents, geofences, ...) are introduced."""
    return None


async def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
