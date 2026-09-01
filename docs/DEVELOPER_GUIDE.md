# Developer Guide — GeoLegalVault

## Repo layout

```
geolegalvault/
├── frontend/          React + Vite + TS + Tailwind SPA
│   └── src/{pages,components,api,hooks,lib,context}/
├── backend/            FastAPI modular monolith
│   ├── app/main.py     app assembly, middleware, /health
│   ├── app/core/       config, security (JWT/Argon2id), rbac, db, deps, logging,
│   │                   errors, rate_limit, security_headers, sentry
│   ├── app/modules/    one package per feature — auth, users, geofences, documents,
│   │                   versions, blockchain, verify, audit, reports — each with
│   │                   router.py (HTTP), service.py (logic), schemas.py (Pydantic),
│   │                   models.py (collection name / enums)
│   ├── app/services/   cross-module infrastructure — hashing, storage (R2/MinIO),
│   │                   blockchain (web3.py), geofence (point-in-polygon)
│   ├── app/workers/    optional anchor-confirmation poller
│   └── tests/{unit,integration,api}/
├── contracts/           Hardhat project — DocumentAnchor.sol, tests, deploy script
├── scripts/              seed.py, backup.sh, faucet_check.py, anchor_smoke_test.py
├── docs/                  this file and its siblings (SRS, API, DB, threat model, …)
├── docker-compose.yml    mongo + minio(+init) + hardhat-node(placeholder) + backend
└── .env.example          single source of truth for every env var
```

## Local setup

Prerequisites: Docker + Docker Compose, Python 3.11+, Node.js 20+.

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
docker compose up -d          # mongo + minio + backend
curl http://localhost:8000/api/v1/health
```

Running backend/frontend outside Docker (hot-reload, faster iteration):

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # or `source .venv/bin/activate`
pip install -r requirements.txt
uvicorn app.main:app --reload

cd frontend
npm install
npm run dev        # http://localhost:5173
```

MinIO console: http://localhost:9001 (login = `STORAGE_ACCESS_KEY` / `STORAGE_SECRET_KEY`
from `.env`, default `minioadmin`/`minioadmin`).

### Exercising the blockchain locally

`docker-compose`'s `hardhat-node` service is a placeholder (just keeps port 8545 open for
`/health` to probe) — it is **not** a real chain. For real anchoring in local dev, run a
real Hardhat node yourself:

```bash
cd contracts
npm install
npx hardhat node                       # separate terminal, keep it running
npx hardhat run scripts/deploy.ts --network localhost   # if you add a `localhost` network
```

Or just point `SEPOLIA_RPC_URL`/`SERVICE_WALLET_PRIVATE_KEY`/`CONTRACT_ADDRESS` at a real
deployed Sepolia contract even for local dev — anchoring is identical code either way.
Without any of these configured, approvals still work but stay `APPROVED` (pending
anchor) — this is intentional fallback behavior, not a bug (see `services/blockchain.py`).

## Seeding data

```bash
python scripts/seed.py --email admin@example.com --password "Str0ngPass!"        # one user
python scripts/seed.py --demo                                                     # one user per role + HQ geofence
python scripts/seed.py --seed-documents                                           # ~35 synthetic docs (needs --demo first)
```
See `scripts/seed.py`'s module docstring for the full flag list, and `DEPLOYMENT.md` for
how this is used against a real cloud deployment.

## Testing

```bash
cd backend && pytest                 # unit + integration + API; coverage report + 60% gate
cd contracts && npx hardhat test
cd frontend && npm run test
```

`backend/tests/conftest.py` runs every test against a real local MongoDB (a dedicated
`geolegalvault_test` database, wiped between tests) — not mocked. It also sets
`RATE_LIMIT_ENABLED=false` before the app is imported, because the shared test transport
would otherwise look like one client hammering the API and trip the global rate limiter
mid-suite; keep that override if you add new middleware with similar global state.

## Linting / conventions

- Backend: `ruff check app tests` (config in `backend/pyproject.toml`, line length 100).
  Style already established in the codebase: module-level docstrings explain *why*, not
  *what*; inline comments only for non-obvious invariants; typed function signatures
  throughout; domain errors are `AppError` subclasses rendered by one shared handler
  (`core/errors.py`), not ad hoc `HTTPException`s (the `auth`/`users` modules are the one
  deliberate exception — see `API.md`'s error-format note).
- Frontend: `npm run lint` (ESLint), TypeScript strict mode via `tsc -b` (part of
  `npm run build`).
- Commit messages: state what changed and why, phase-oriented where relevant (see `git
  log` for the established pattern — each phase of `IMPLEMENTATION_PROMPT.md` is roughly
  one commit).

## Contributing

- One deployable backend (modular monolith) — do not split a module out into a separate
  service without a strong reason; the plan explicitly scopes this project as *not*
  microservices (Guardrail #10).
- `document_versions` and `audit_logs` are insert-only/append-only by construction: if you
  need a new field, add a new whitelisted setter function in the relevant `service.py`
  rather than opening up a generic update path.
- Every new protected endpoint must declare a `core.rbac.require(permission)` dependency —
  there is no "protected by default" fallback; an endpoint with no permission check is
  reachable by any authenticated user, which is very likely not what you want (this is
  what `tests/api/test_authz_matrix.py` exists to catch).
- Any endpoint that performs a sensitive operation (upload/download/approve/amend) must
  also depend on `require_geofence` — never trust a client-supplied location "allowed"
  flag.
- Write tests in the same change as the code (Guardrail #11) — this codebase has no
  "add tests later" backlog.
- Never write "military-grade," "tamper-proof," "unhackable," or "guaranteed location" in
  code, comments, docs, or UI text — see `THREAT_MODEL.md` for the vocabulary to use
  instead ("tamper-evident," "policy-level geofencing," "prototype-grade").
- Branching: trunk-based-lite — short-lived `feature/*` branches, PR into `main`, CI green
  required before merge.
