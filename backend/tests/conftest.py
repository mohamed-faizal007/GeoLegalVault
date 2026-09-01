"""Shared pytest fixtures.

Tests run against a real (local) MongoDB — the one docker-compose exposes on
localhost:27017 per .env — but a dedicated `geolegalvault_test` database, so
they never touch dev data. Every test gets a clean database.
"""

import os

os.environ.setdefault("MONGODB_DB", "geolegalvault_test")
# Every request in this test suite shares one ASGI transport with no real
# client address, so the global rate limiter (app/core/rate_limit.py) would
# otherwise bucket the whole run as a single client and start rejecting
# unrelated tests once the suite crosses RATE_LIMIT_PER_MIN requests.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import httpx
import pytest_asyncio

from app.core.db import ensure_indexes, get_database
from app.main import app


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _indexes() -> None:
    await ensure_indexes()


@pytest_asyncio.fixture(autouse=True)
async def _clean_database():
    db = get_database()
    for name in await db.list_collection_names():
        await db[name].delete_many({})
    yield


@pytest_asyncio.fixture
def db():
    return get_database()


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
