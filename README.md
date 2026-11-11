# GeoLegalVault

Geospatially-aware document integrity & lifecycle platform. See `docs/GeoLegalVault_Project_Plan.md`
(architecture) and `docs/IMPLEMENTATION_PROMPT.md` (phase-by-phase build script) for the full design.

All 12 phases are implemented: auth/RBAC, geofence enforcement, storage/hashing/versioning,
smart-contract anchoring on Sepolia, the full lifecycle workflow, the 3-way tamper-detection
verification loop, audit logging, the full frontend, admin/reporting, a test suite with CI (370 backend, 146 frontend, 9 contract cases as of 2026-11-11; see `docs/TEST_PLAN.md`),
and deployment docs. See `docs/` for the full documentation set — start with `docs/SRS.md` (what
it does), `docs/DEMO_SCRIPT.md` (see it work), `docs/DEPLOYMENT.md` (ship it), and
`docs/DEVELOPER_GUIDE.md` (work on it).

## Demo accounts

The five demo users (`legal_officer@geolegalvault.demo`, `authorized_staff@geolegalvault.demo`,
`reviewing_officer@geolegalvault.demo`, `auditor@geolegalvault.demo`, `administrator@geolegalvault.demo`)
share one demo password. It is not written in this README. It is the `DEMO_PASSWORD` constant in
`scripts/seed.py` (created and printed by `python scripts/seed.py --demo`); no document in the repository repeats it.
Do not reuse it anywhere real.

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

This starts MongoDB, RustFS (S3-compatible object storage; MinIO's images are gone, see DECISIONS.md D-034), a placeholder `hardhat-node`
container (it only keeps port 8545 open for `/health`; it is not a blockchain, see `docs/DEVELOPER_GUIDE.md`), and the FastAPI backend. Once it's up:

```bash
curl http://localhost:8000/api/v1/health
```

RustFS console: http://localhost:9001 (login with `STORAGE_ACCESS_KEY` / `STORAGE_SECRET_KEY` from `.env`).

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

Open http://localhost:5173 and sign in (create the demo users first with `python scripts/seed.py --demo`; see "Demo accounts" above).

## Project layout

See `docs/DEVELOPER_GUIDE.md` for the annotated repo layout, or
`docs/IMPLEMENTATION_PROMPT.md` → "TARGET REPOSITORY STRUCTURE" for the original target.

## Documentation

| Doc | Covers |
|---|---|
| `docs/SRS.md` | Requirements, actors, acceptance criteria |
| `docs/API.md` | Endpoint reference, auth flow, error catalogue |
| `docs/DB_DESIGN.md` | MongoDB collections, indexes, geospatial queries |
| `docs/THREAT_MODEL.md` | Assets, threats, mitigations, honest limitations |
| `docs/TEST_PLAN.md` | Test strategy, coverage, current results |
| `docs/DEPLOYMENT.md` | Exact deploy sequence (Sepolia → Atlas → R2 → Render → Vercel) |
| `docs/USER_GUIDE.md` | What each role can do, per page |
| `docs/DEVELOPER_GUIDE.md` | Local setup, conventions, contributing |
| `docs/RESEARCH.md` | Research question, method, metrics, baselines, limitations |
| `docs/DEMO_SCRIPT.md` | The 10-minute live demo, minute by minute |

## Guardrails

This project follows a fixed set of security and scope guardrails (documents stay off-chain,
service-wallet-only anchoring, server-side geofence enforcement, immutable versions, no
"military-grade"/"tamper-proof" claims, etc.) — see `CLAUDE.md` and the top of
`docs/IMPLEMENTATION_PROMPT.md` for the full list.
