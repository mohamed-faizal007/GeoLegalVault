import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.body_limit import BodyLimitMiddleware
from app.core.config import get_settings
from app.core.db import close_client, ensure_indexes, get_database, ping_mongo
from app.core.errors import register_exception_handlers
from app.core.health import check_chain, check_storage
from app.core.logging import JSONLoggingMiddleware
from app.core.rate_limit import RateLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.sentry import init_sentry
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.blockchain.router import router as blockchain_router
from app.modules.documents.router import router as documents_router
from app.modules.geofences.router import router as geofences_router
from app.modules.reports.router import router as reports_router
from app.modules.users.router import router as users_router
from app.modules.verify.router import router as verify_router
from app.modules.versions.router import router as versions_router
from app.workers import heartbeat as anchor_worker_heartbeat

settings = get_settings()
init_sentry()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.APP_ENV != "development" and settings.geofence_bbox is None:
        logging.getLogger(__name__).warning(
            "GEOFENCE_ALLOWED_BBOX is not set: a swapped [lat, lng] geofence whose "
            "longitude is within +/-90 cannot be detected (Guardrail #9, D-027)"
        )
    await ensure_indexes()
    yield
    await close_client()


app = FastAPI(title="GeoLegalVault API", version="0.1.0", lifespan=lifespan)

app.add_middleware(JSONLoggingMiddleware)
# Size cap (Guardrail #5): wraps the logger and the app so nothing reads the body past
# the limit, but sits inside CORS/security headers so a 413 still carries them.
app.add_middleware(BodyLimitMiddleware)
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(RateLimitMiddleware, requests_per_min=settings.RATE_LIMIT_PER_MIN)
app.add_middleware(SecurityHeadersMiddleware, hsts=settings.APP_ENV != "development")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(geofences_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(versions_router, prefix="/api/v1")
app.include_router(blockchain_router, prefix="/api/v1")
app.include_router(verify_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")

register_exception_handlers(app)


@app.get("/api/v1/health")
async def health() -> dict:
    mongo_ok = await ping_mongo()
    storage_ok = await check_storage(settings.STORAGE_ENDPOINT)
    # Hardhat node isn't implemented until Phase 5, so an unreachable chain
    # node is expected pre-Phase-5 and reported as "degraded", not an error.
    chain_ok = await check_chain(settings.CHAIN_RPC_URL)
    # A bare ok/stale flag (this endpoint is unauthenticated). The worker is optional
    # (Guardrail #10), so a stale one never changes the overall status (D-040).
    try:
        worker_ok = mongo_ok and await anchor_worker_heartbeat.is_fresh(get_database())
    except Exception:
        worker_ok = False

    return {
        "status": "ok" if mongo_ok and storage_ok else "degraded",
        "mongo": "reachable" if mongo_ok else "unreachable",
        "storage": "reachable" if storage_ok else "unreachable",
        "chain": "reachable" if chain_ok else "degraded",
        "anchor_worker": "ok" if worker_ok else "stale",
    }
