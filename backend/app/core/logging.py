"""Structured JSON request logging middleware."""

import json
import logging
import sys
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

logger = logging.getLogger("geolegalvault")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.propagate = False


class JSONLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        payload = json.dumps(
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            }
        )
        # 4xx covers the security-relevant denials (auth failures, RBAC
        # FORBIDDEN, GEOFENCE_DENIED, bad uploads); 5xx is a hard failure
        # (e.g. storage/chain unreachable). Both get flagged above the
        # normal per-request INFO line so they're easy to alert on.
        if response.status_code >= 500:
            logger.error(payload)
        elif response.status_code >= 400:
            logger.warning(payload)
        else:
            logger.info(payload)
        return response
