FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libmagic1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/v1/health || exit 1

# gunicorn + uvicorn workers (production-ready: process-level concurrency,
# worker recycling, graceful reload) instead of bare `uvicorn` (fine for
# local dev — see docker-compose.yml — but single-process). $PORT is set by
# Render at runtime; $WEB_CONCURRENCY defaults to 2, sized for a free-tier
# instance (Plan Part 23's cost target) — raise it if the instance has more
# CPU/RAM headroom.
CMD gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers ${WEB_CONCURRENCY:-2} \
    --bind 0.0.0.0:${PORT:-8000} \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
