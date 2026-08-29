# GeoLegalVault

Geospatially-aware document integrity & lifecycle platform. See `docs/GeoLegalVault_Project_Plan.md`
(architecture) and `docs/IMPLEMENTATION_PROMPT.md` (phase-by-phase build script) for the full design.

Currently implemented: **Phase 0 — scaffolding, environment, health check.**

## Prerequisites

- Docker + Docker Compose
- Node.js 20+ and npm (for local frontend dev outside Docker)
- Python 3.11+ (for local backend dev outside Docker)

## Environment setup

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

Edit `.env` and fill in real values before deploying anywhere beyond local dev. In local dev
(`APP_ENV=development`), placeholder values are fine — the backend only rejects placeholders when
`APP_ENV` is not `development`.

## Run everything with Docker Compose

```bash
docker-compose up
```

This starts MongoDB, MinIO (S3-compatible object storage), a placeholder Hardhat node service
(implemented in Phase 5), and the FastAPI backend. Once it's up:

```bash
curl http://localhost:8000/api/v1/health
```

MinIO console: http://localhost:9001 (login with `STORAGE_ACCESS_KEY` / `STORAGE_SECRET_KEY` from `.env`).

## Run the backend locally (without Docker)

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate   # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend tests: `pytest`. Lint: `ruff check app tests`.

## Run the frontend locally

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — it calls the backend's `/api/v1/health` and renders the JSON response.

## Project layout

See `docs/IMPLEMENTATION_PROMPT.md` → "TARGET REPOSITORY STRUCTURE" for the full monorepo layout.
Most module/service files outside `backend/app/core` are currently empty stubs; they're filled in
phase by phase per `docs/IMPLEMENTATION_PROMPT.md`.

## Guardrails

This project follows a fixed set of security and scope guardrails (documents stay off-chain,
service-wallet-only anchoring, server-side geofence enforcement, immutable versions, no
"military-grade"/"tamper-proof" claims, etc.) — see `CLAUDE.md` and the top of
`docs/IMPLEMENTATION_PROMPT.md` for the full list.
