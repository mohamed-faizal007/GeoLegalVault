from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import close_client, ensure_indexes, ping_mongo
from app.core.logging import JSONLoggingMiddleware

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


@app.get("/api/v1/health")
async def health() -> dict:
    mongo_ok = await ping_mongo()
    return {
        "status": "ok" if mongo_ok else "degraded",
        "mongo": "reachable" if mongo_ok else "unreachable",
        # storage/blockchain clients aren't wired up until Phases 4/5.
        "storage": "not_configured",
        "chain": "not_configured",
    }
