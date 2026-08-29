from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import close_client, ensure_indexes, ping_mongo
from app.core.health import check_chain, check_storage
from app.core.logging import JSONLoggingMiddleware
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await ensure_indexes()
    yield
    await close_client()


app = FastAPI(title="GeoLegalVault API", version="0.1.0", lifespan=lifespan)

app.add_middleware(JSONLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health() -> dict:
    mongo_ok = await ping_mongo()
    storage_ok = await check_storage(settings.STORAGE_ENDPOINT)
    # Hardhat node isn't implemented until Phase 5, so an unreachable chain
    # node is expected pre-Phase-5 and reported as "degraded", not an error.
    chain_ok = await check_chain(settings.CHAIN_RPC_URL)

    return {
        "status": "ok" if mongo_ok and storage_ok else "degraded",
        "mongo": "reachable" if mongo_ok else "unreachable",
        "storage": "reachable" if storage_ok else "unreachable",
        "chain": "reachable" if chain_ok else "degraded",
    }
