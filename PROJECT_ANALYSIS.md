# PROJECT_ANALYSIS.md — GeoLegalVault

*Full from-scratch codebase analysis. Written as a persistent reference; paths are repo-relative unless stated otherwise.*

---

## 1. PROJECT OVERVIEW

### Purpose & value proposition

GeoLegalVault is a **geospatially-aware legal document integrity and lifecycle platform**. It lets an organization with a fixed physical location (e.g. a government registry office, a law firm HQ) manage sensitive legal documents through a controlled lifecycle (draft → submit → review → approve → blockchain-anchor → active → amend/archive), while enforcing two independent trust guarantees:

1. **Geofencing** — sensitive operations (upload, approve, amend) can only be performed by a user physically present inside an assigned GPS polygon, enforced **server-side** (never trusting a client-asserted allow/deny flag).
2. **Blockchain-anchored tamper detection** — every approved document version's SHA-256 hash is written to a minimal Ethereum smart contract (Sepolia testnet). A 3-way verification loop later recomputes the hash from the actual stored bytes and compares it against both the database record and the on-chain record, so neither a database compromise nor a storage compromise alone can produce a false "verified" result.

Target users are the five RBAC roles seeded in the demo data: **Legal Officer**, **Authorized Staff**, **Reviewing Officer**, **Auditor**, **Administrator** — modeling a real maker-checker legal workflow (e.g. a land-records or contracts office) rather than a generic DMS.

The project explicitly avoids overclaiming: `README.md` and `CLAUDE.md`/`docs/IMPLEMENTATION_PROMPT.md` guardrails forbid words like "tamper-proof" or "military-grade" — the docs describe this as geofencing being "a policy/defense-in-depth control, not a security guarantee" (browser GPS is spoofable), which is an unusually honest design stance for a project like this.

### Tech stack

| Layer | Stack |
|---|---|
| Backend | Python 3.11+, FastAPI 0.115.6, Motor 3.6.0 (async MongoDB driver), Pydantic 2.10.4 / pydantic-settings 2.7.0, PyJWT 2.10.1, argon2-cffi 23.1.0, boto3 1.35.90 (S3/R2 client), web3.py 7.6.1, python-magic (MIME sniffing), Uvicorn/Gunicorn |
| Frontend | React 18.3.1, TypeScript 5.7, Vite 6.0.5, React Router 7.0.2, TanStack Query 5.62, Tailwind CSS 3.4.17, Vitest 4.1.11 + Testing Library |
| Smart contract | Solidity ^0.8.20, Hardhat 2.22.10 + `@nomicfoundation/hardhat-toolbox` 5, TypeScript, deployed to Ethereum **Sepolia** testnet |
| Database | MongoDB 7 (with 2dsphere geospatial indexes for geofence polygons, text index for document search) |
| Object storage | S3-compatible — MinIO for local dev, **Cloudflare R2** in production |
| Infra/deploy | Docker + docker-compose (local), Render (backend), Vercel (frontend), MongoDB Atlas M0 (prod DB), Sentry (optional error tracking) |
| CI | GitHub Actions (`.github/workflows/ci.yml`) — three parallel jobs: backend (pytest+ruff), contracts (Hardhat test), frontend (eslint+vitest+build) |

### Architecture

```
                       ┌─────────────────────┐
                       │   React Frontend     │  (Vite, :5173)
                       │  RBAC-gated routes    │
                       └──────────┬───────────┘
                                  │ REST (JWT bearer, X-Geo-* headers)
                                  ▼
                       ┌─────────────────────┐
                       │  FastAPI Backend      │  (:8000, "modular monolith")
                       │  modules/: auth, users,│
                       │  documents, versions,  │
                       │  geofences, blockchain,│
                       │  verify, audit, reports│
                       └───┬─────────┬────────┬─┘
                           │         │        │
              ┌────────────┘         │        └────────────┐
              ▼                      ▼                     ▼
     ┌────────────────┐   ┌──────────────────┐   ┌──────────────────────┐
     │ MongoDB 7       │   │ S3-compatible     │   │ web3.py → Sepolia RPC │
     │ (Motor async)   │   │ storage (MinIO/R2)│   │ (Alchemy) → service   │
     │ 2dsphere/text    │   │ encrypted bucket, │   │ wallet signs anchor() │
     │ indexes          │   │ server-generated  │   │ tx on DocumentAnchor  │
     │ documents,       │   │ keys, presigned    │   │ .sol contract         │
     │ document_versions,│  │ download URLs     │   └──────────┬────────────┘
     │ geofences,        │  └──────────────────┘              │
     │ blockchain_anchors,│                                    ▼
     │ verification_records,│                        ┌──────────────────────┐
     │ audit_logs, sessions │                        │ Sepolia (Ethereum L1  │
     └──────────────────────┘                        │ testnet) — immutable   │
                                                       │ (documentId,version)→ │
                                                       │ hash mapping           │
                                                       └──────────────────────┘
```

Backend is a single FastAPI "modular monolith" (not microservices) — each business area under `backend/app/modules/<name>/` has its own `router.py` (HTTP), `service.py` (business logic), `schemas.py` (Pydantic I/O models), `models.py` (Mongo collection name/enum constants). Cross-cutting concerns (auth deps, RBAC, rate limiting, security headers, error envelope, logging, Sentry) live in `backend/app/core/`. Chain and storage clients live in `backend/app/services/` (thin, stateless wrappers) so multiple modules can share them without circular imports.

There is exactly one component that writes to the chain: the service wallet inside `app/services/blockchain.py`, invoked only from `documents/workflow.py::approve()`. There is no user-facing MetaMask/wallet-connect flow anywhere — a deliberate simplification (Guardrail #3 in `docs/IMPLEMENTATION_PROMPT.md`).

---

## 2. STRUCTURE & CODE MAP

### Top-level layout

```
GeoLegalVault/
├── backend/                 FastAPI app (Python)
│   ├── app/
│   │   ├── main.py                  FastAPI app factory, middleware, /health
│   │   ├── core/                    config, db, deps, rbac, security, errors, logging,
│   │   │                            rate_limit, security_headers, sentry, health
│   │   ├── modules/
│   │   │   ├── auth/                login, refresh rotation+reuse detection, logout
│   │   │   ├── users/                CRUD, role assignment, geofence assignment (admin)
│   │   │   ├── documents/            upload, list/search, lifecycle workflow.py (state machine)
│   │   │   ├── versions/             immutable version records (V1, V2, …)
│   │   │   ├── geofences/            2dsphere polygon CRUD + admin management
│   │   │   ├── blockchain/           anchor bookkeeping (Mongo side of on-chain anchors)
│   │   │   ├── verify/               the 3-way verification loop (core feature)
│   │   │   ├── audit/                append-only audit log (query only, no update/delete route)
│   │   │   └── reports/              read-only aggregation endpoints for admin dashboard
│   │   ├── services/                 storage.py (S3/MinIO), blockchain.py (web3.py), hashing.py,
│   │   │                             geofence.py (point-in-polygon dependency)
│   │   └── workers/                  anchor_confirmer.py — optional background poller for anchors
│   │                                 still PENDING after the synchronous confirm window (excluded
│   │                                 from coverage gate on purpose, see pyproject.toml)
│   ├── tests/                        unit/, integration/ (real Mongo/MinIO/Hardhat), api/ (authz matrix)
│   ├── Dockerfile, requirements.txt, pyproject.toml (ruff + pytest config)
│
├── frontend/                 React + Vite app (TypeScript)
│   ├── src/
│   │   ├── App.tsx                   route table, ProtectedRoute-wrapped permission gates
│   │   ├── main.tsx                  entry point
│   │   ├── api/                      one file per backend module (http.ts = axios/fetch wrapper)
│   │   ├── context/AuthContext.tsx   JWT/session state, refresh handling
│   │   ├── hooks/useGeoLocation.ts   browser Geolocation API wrapper
│   │   ├── components/               Layout, Sidebar, ProtectedRoute, LocationGate, FileDropzone,
│   │   │                             StatusBadge, admin/ (GeofenceManagementPanel, HealthPanel,
│   │   │                             ReportsPanel, UserManagementPanel)
│   │   ├── pages/                    Login, Dashboard, DocumentRepository, Upload, DocumentDetails,
│   │   │                             VersionHistory, AmendmentRequest, Verification,
│   │   │                             BlockchainVerification, GeofenceStatus, AuditLogs, AdminPanel,
│   │   │                             Settings, Forbidden, NotFound
│   │   └── lib/                      permissions.ts (mirrors backend RBAC map), jwt.ts, format.ts,
│   │                                 errorMessages.ts, authToken.ts, env.ts
│
├── contracts/                 Hardhat + Solidity project
│   ├── contracts/DocumentAnchor.sol  the entire on-chain surface (74 lines)
│   ├── test/DocumentAnchor.test.ts   Hardhat/Mocha contract tests
│   ├── scripts/deploy.ts             Sepolia deploy script
│   └── hardhat.config.ts             networks (sepolia via dotenv), typechain
│
├── scripts/                   Ops/demo tooling
│   ├── seed.py                       user/demo/`--seed-documents` seeding (370 lines)
│   ├── backup.sh                     Mongo + storage backup (Phase 12)
│   ├── anchor_smoke_test.py          one-off real Sepolia anchor+read-back sanity check
│   └── faucet_check.py               (1 line — see Current State, likely incomplete stub)
│
├── docs/                      Extensive doc set: SRS, API, DB_DESIGN, THREAT_MODEL, TEST_PLAN,
│                              DEPLOYMENT, USER_GUIDE, DEVELOPER_GUIDE, RESEARCH, DEMO_SCRIPT,
│                              GeoLegalVault_Project_Plan.md, IMPLEMENTATION_PROMPT.md, info.md
│
├── docker-compose.yml         mongo, minio, minio-init, hardhat-node (placeholder), backend
├── .env.example / frontend/.env.example
├── .github/workflows/ci.yml   backend / contracts / frontend jobs
└── CLAUDE.md                  EMPTY (0 bytes) — see Current State
```

### Entry points

- Backend: `backend/app/main.py` — `uvicorn app.main:app`. Exposes `/api/v1/health` plus 9 routers all mounted under `/api/v1` prefix (auth, users, geofences, documents, versions, blockchain, verify, audit, reports).
- Frontend: `frontend/src/main.tsx` → `App.tsx` (route table) → `frontend/index.html` / Vite dev server on :5173.
- Contracts: `contracts/scripts/deploy.ts` (Sepolia deploy), `contracts/contracts/DocumentAnchor.sol` (the only contract).
- Ops: `scripts/seed.py` (user/demo provisioning), `scripts/backup.sh`, `scripts/anchor_smoke_test.py`.

### Key data flow (documents lifecycle)

1. **Upload** (`documents/router.py` → `documents/service.py::create_document_with_v1`): validates size (`MAX_UPLOAD_MB`) and MIME (claimed content-type vs `python-magic` byte-sniffed detection, `ALLOWED_MIME_TYPES` allowlist in `backend/app/modules/documents/service.py:30-39`) → stores object under a **server-generated key** (`storage.build_version_key`, never the client filename — defeats path traversal) → computes SHA-256 → inserts `documents` doc (status `DRAFT`) + `document_versions` V1 atomically-ish (rolls back the document insert if the version insert fails, `service.py:152-166`).
2. **Lifecycle** (`documents/workflow.py`, a hand-rolled state machine): `submit()` (owner only, DRAFT→SUBMITTED) → `review()` (reviewer ≠ uploader enforced via `enforce_maker_checker`, SUBMITTED→UNDER_REVIEW→PENDING_APPROVAL or →CHANGES_REQUESTED→DRAFT) → `approve()` (approver ≠ uploader, PENDING_APPROVAL→APPROVED, **then automatically anchors on-chain** — no user-triggered "anchor" endpoint exists anywhere) → `promote_confirmed_anchor()` (APPROVED→BLOCKCHAIN_ANCHORED→ACTIVE once confirmed, retires the previously-ACTIVE version to SUPERSEDED without mutating it) → `request_amendment()` (ACTIVE→AMENDMENT_REQUESTED) → new upload creates V(n+1) → `archive()` (ACTIVE→ARCHIVED, hides from default `list_documents` but retains all versions/anchors, see `documents/service.py:200-206`).
3. **Anchoring** (`services/blockchain.py`): builds/signs/sends `anchor(documentId, version, sha256Bytes32, eventType)` tx with the single **service wallet** (nonce-serialized via an `asyncio.Lock`), retried up to `ANCHOR_MAX_ATTEMPTS`, polled for confirmation up to `ANCHOR_CONFIRM_POLL_ATTEMPTS` times; on any failure the document simply stays `APPROVED` with `anchor_pending_alert=True` rather than the request erroring — `documents/workflow.py::approve()` never raises on chain failure (comment at lines 218-219 makes this explicit).
4. **Verification** (`verify/service.py::verify_version`, the product's headline feature): reads the actual current bytes from storage → recomputes SHA-256 → reads the on-chain hash live via `chain.get_onchain_anchor()` → compares recomputed vs. stored-in-Mongo vs. on-chain using constant-time `hmac.compare_digest` → returns `VERIFIED` / `MISMATCH` / `NOT_ANCHORED`. A `MISMATCH` permanently flags the document `integrity_flag="TAMPERED"` (only clearable by hand, never automatically, `documents/service.py:262-271`).
5. **Geofencing** (`services/geofence.py::require_geofence` FastAPI dependency, used on upload/approve/amend routes): extracts `{lat,lng,accuracy,timestamp}` from either `X-Geo-*` headers or the request body, validates ranges, **fails closed** on accuracy > `GEO_ACCURACY_MAX_M` (422) or staleness > `GEO_FRESHNESS_MAX_SEC` (422), then runs a real MongoDB `$geoIntersects` query against the user's `assigned_geofence_ids`. A denial is itself audit-logged (`GEOFENCE_DENIED`).
6. **Audit** (`audit/service.py`, `audit/router.py`): every significant action across every module calls `audit.record(...)`; the router only exposes read/query endpoints (`GET`), gated to `Auditor`/`Administrator` via `AUDIT_VIEW` permission — there is no update or delete route, enforcing append-only by omission rather than a DB-level immutability guarantee.
7. **RBAC** (`core/rbac.py`): a deny-by-default permission map (`ROLE_PERMISSIONS`) keyed by 5 roles → permission-string sets; the `require(permission)` FastAPI dependency reads the role from the **freshly loaded DB user**, not the JWT payload, so a role change/deactivation takes effect on the very next request rather than waiting for token expiry (`rbac.py:83-86`). `enforce_maker_checker` is the shared primitive behind maker≠checker on both review and approve.

### Config files & env vars

| File | Purpose |
|---|---|
| `.env` / `.env.example` (repo root) | Backend config: `APP_ENV`, `JWT_SECRET`, `JWT_ACCESS_TTL_MIN`/`JWT_REFRESH_TTL_DAYS`, `MONGODB_URI`/`MONGODB_DB`, `STORAGE_*` (endpoint/public endpoint/region/bucket/keys/presign TTL), `MAX_UPLOAD_MB`, `SEPOLIA_RPC_URL`, `SERVICE_WALLET_PRIVATE_KEY`, `CONTRACT_ADDRESS`, `CHAIN_ID`, `ANCHOR_*` (confirmations, max attempts, retry backoff, poll attempts/interval), `CHAIN_RPC_URL` (local dev only), `GEO_ACCURACY_MAX_M`, `GEO_FRESHNESS_MAX_SEC`, `SENTRY_DSN`, `CORS_ORIGINS`, `RATE_LIMIT_PER_MIN`. Also read by `contracts/hardhat.config.ts` via `dotenv` for `SEPOLIA_RPC_URL`/`SERVICE_WALLET_PRIVATE_KEY` (no separate `contracts/.env`). |
| `frontend/.env` / `.env.example` | `VITE_API_BASE_URL` (only one var). |
| `backend/app/core/config.py` | Pydantic-settings `Settings` class; **fails fast outside `development`** if any of `JWT_SECRET`, `MONGODB_URI`, `STORAGE_ACCESS_KEY`/`SECRET_KEY`, `SEPOLIA_RPC_URL`, `SERVICE_WALLET_PRIVATE_KEY`, `CONTRACT_ADDRESS` is still a placeholder (`"change_me"`/`"0xCHANGE_ME"`/empty/contains "CHANGE_ME"). Resolves `.env` via an **absolute** repo-root path (`Path(__file__).resolve().parents[3]`), explicitly to avoid CWD-relative surprises. |
| `backend/pyproject.toml` | Ruff (`E,F,I,UP,B` rules, line-length 100) + pytest config (`--cov=app --cov-fail-under=60`, session-scoped asyncio loop, `app/workers/*` excluded from coverage). |
| `docker-compose.yml` | 5 services: `mongo` (7, healthcheck), `minio` + `minio-init` (one-shot bucket creation), `hardhat-node` (a **placeholder** container — just `tail -f /dev/null`, kept only so `/health` has something to probe at :8545; the *real* chain target is always Sepolia), `backend` (overrides `MONGODB_URI`/`STORAGE_ENDPOINT`/`CHAIN_RPC_URL` to Docker-internal service names). |
| `.github/workflows/ci.yml` | 3 jobs (backend/contracts/frontend); backend job additionally installs+compiles `contracts/` because `tests/integration/test_anchor.py` spins up a **real local Hardhat node**, not a mock. |

---

## 3. DEPENDENCIES & SETUP

### Backend (`backend/requirements.txt`)

| Package | Version | Used for |
|---|---|---|
| fastapi | 0.115.6 | Web framework / routing / dependency injection |
| uvicorn[standard] | 0.34.0 | ASGI dev server |
| gunicorn | 23.0.0 | Production process manager (see `backend/Dockerfile`) |
| motor | 3.6.0 | Async MongoDB driver |
| pydantic | 2.10.4 | Schemas / validation |
| pydantic-settings | 2.7.0 | `.env`-backed `Settings` |
| pyjwt | 2.10.1 | Access/refresh token signing & verification |
| argon2-cffi | 23.1.0 | Password hashing (Argon2id) |
| boto3 | 1.35.90 | S3-compatible client (MinIO/R2) — presigned URLs, put/get object |
| web3 | 7.6.1 | Ethereum RPC client, contract calls, tx signing |
| python-magic-bin (win32) / python-magic (else) | 0.4.14 / 0.4.27 | Magic-byte MIME sniffing for upload validation |
| python-multipart | 0.0.20 | multipart/form-data parsing (file uploads) |
| httpx | 0.28.1 | Async test client / outbound HTTP |
| sentry-sdk[fastapi] | 2.19.2 | Optional error tracking (`SENTRY_DSN`) |
| pytest / pytest-asyncio / pytest-cov | 8.3.4 / 0.25.0 / 6.0.0 | Test suite + coverage |
| ruff | 0.8.4 | Lint |

Also transitively required (per `backend/app/services/blockchain.py`): `eth_account` (comes with `web3`). Not in requirements.txt explicitly but bundled — confirmed no separate pin issue found.

### Frontend (`frontend/package.json`)

Dependencies: `@tanstack/react-query` 5.62 (server-state/data fetching), `react`/`react-dom` 18.3.1, `react-router-dom` 7.0.2 (routing).
DevDependencies: `vite` 6.0.5 + `@vitejs/plugin-react` (build/dev server), `typescript` 5.7.2, `tailwindcss` 3.4.17 + `autoprefixer`/`postcss` (styling), `eslint` 9.17 + `@eslint/js` + `typescript-eslint` 8.68 + `eslint-plugin-react-hooks`/`react-refresh` (lint — git log notes this "caught 2 React bugs" in Phase 11), `vitest` 4.1.11 + `@testing-library/react`/`jest-dom`/`user-event` + `jsdom` (component tests).

### Contracts (`contracts/package.json`)

`@nomicfoundation/hardhat-toolbox` 5 (ethers, chai matchers, gas reporter, typechain bundle), `hardhat` 2.22.10, `dotenv` 16.4.5 (reads root `.env` for Sepolia RPC/key), `ts-node` + `typescript` 5.5.4.

### External services / accounts required

- **MongoDB** — Atlas M0 in prod, local Mongo 7 container in dev.
- **S3-compatible object storage** — Cloudflare R2 in prod, MinIO in dev (console at :9001).
- **Ethereum Sepolia RPC** — Alchemy (or similar) — `SEPOLIA_RPC_URL`.
- **A funded Sepolia service wallet** — `SERVICE_WALLET_PRIVATE_KEY`; needs faucet ETH (`docs/DEPLOYMENT.md` mentions Google Cloud/Alchemy/sepoliafaucet.com faucets; `docs/info.md` and `scripts/faucet_check.py` reference this too).
- **Sentry** (optional) — `SENTRY_DSN`, only used if set.
- Render (backend hosting), Vercel (frontend hosting) — only needed for the production deploy path, not local dev.

### Verified from-scratch setup & run steps

These are copied/confirmed directly against `README.md` and the actual `package.json`/`pyproject.toml` scripts — they match:

```bash
# 1. Env files
cp .env.example .env
cp frontend/.env.example frontend/.env
# Edit .env — placeholders are fine in APP_ENV=development.

# 2a. Everything via Docker Compose
docker-compose up
curl http://localhost:8000/api/v1/health
# MinIO console: http://localhost:9001 (STORAGE_ACCESS_KEY/SECRET_KEY from .env)

# 2b. Backend locally (without Docker)
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; source .venv/bin/activate elsewhere
pip install -r requirements.txt
uvicorn app.main:app --reload
# Tests: pytest        (gate: --cov-fail-under=60, per pyproject.toml)
# Lint:  ruff check app tests

# 2c. Frontend locally
cd frontend
npm install
npm run dev             # http://localhost:5173
npm run build            # tsc -b && vite build
npm run lint              # eslint .
npm run test               # vitest run

# 2d. Contracts
cd contracts
npm ci
npx hardhat compile
npx hardhat test
npx hardhat run scripts/deploy.ts --network sepolia   # requires funded wallet + real RPC in root .env

# 2e. Seed demo data (after backend + Mongo are reachable)
python scripts/seed.py --demo                 # 5 role users + HQ geofence, prints demo password
python scripts/seed.py --seed-documents         # synthetic corpus for DEMO_SCRIPT.md (needs --demo first
                                                  #  + real Sepolia config for amendment/tamper cases)

# 2f. Backup (Phase 12, ops)
bash scripts/backup.sh
```

Demo credentials (from `docs/info.md`, all share one password):
```
legal_officer@geolegalvault.demo      → Demo@Pass123!
authorized_staff@geolegalvault.demo   → Demo@Pass123!
reviewing_officer@geolegalvault.demo  → Demo@Pass123!
auditor@geolegalvault.demo            → Demo@Pass123!
administrator@geolegalvault.demo      → Demo@Pass123!
```

---

## 4. CURRENT STATE

### Fully working (verified by reading the actual implementation, not just docs)

- JWT auth: Argon2id hashing, algorithm-pinned verification (rejects `alg: none`), refresh-token rotation **with reuse detection that revokes the whole session family** (`backend/app/modules/auth/service.py:146-186`) — a genuinely solid implementation, not a toy.
- Deny-by-default RBAC across 5 roles with a maker≠checker guard shared between review and approve (`backend/app/core/rbac.py`).
- Real geofence enforcement via MongoDB `$geoIntersects` + accuracy/freshness fail-closed checks (`backend/app/services/geofence.py`).
- Upload pipeline: size cap, claimed-vs-detected MIME cross-check via `python-magic`, server-generated storage keys (defeats path traversal / filename-based attacks).
- Full lifecycle state machine with illegal-transition rejection (409) and audit logging at every step (`backend/app/modules/documents/workflow.py`).
- On-chain anchoring against a real (if minimal) Solidity contract, with nonce-serialized sending, retry/backoff, and a bounded synchronous confirmation window that gracefully degrades to "stays pending" rather than blocking or erroring.
- The 3-way verification loop, using `hmac.compare_digest` (constant-time) for hash comparisons — a nice touch, avoids timing side-channels even though the practical risk here is low.
- Append-only audit log with no update/delete route.
- Reports aggregation endpoint (status/doc-type counts, anchoring success rate, recent verification stats, geofence-denial count) via Mongo aggregation pipelines — read-only by construction.
- Full frontend: RBAC-gated navigation/routes (`frontend/src/App.tsx`, `ProtectedRoute`), a location-gate component, verify-result color coding (green/red/grey), document repository/versions/audit/admin pages.
- CI pipeline exercising all three parts (backend/contracts/frontend) with **no mocking of Mongo/MinIO/the chain** in integration tests — CI spins up a real local Hardhat node.

### Incomplete / stubbed / notable gaps

- **`CLAUDE.md` is completely empty (0 bytes)** at the repo root, despite `README.md`'s "Guardrails" section explicitly pointing to it ("see `CLAUDE.md` ... for the full list") — the referenced guardrails document does not actually exist. This is the single most obvious inconsistency in the repo.
- **`scripts/faucet_check.py` is only 1 line long** — almost certainly a stub/placeholder rather than a working faucet-balance checker, despite being referenced in the deployment workflow context. Worth opening and confirming its single line does something useful (e.g., just a `print("TODO")` or a partial import) before relying on it.
- **`hardhat-node` in `docker-compose.yml` is an explicit placeholder** (`command: ["sh","-c","echo 'hardhat-node: placeholder...' && tail -f /dev/null"]`, lines 57-59) — it exists only so `/health` has something to probe at :8545; it is not a real chain and nothing depends on it being one. The real target is always Sepolia, or a manually-run `npx hardhat node` for local integration tests. This is documented honestly in comments, not hidden, but a newcomer skimming `docker-compose.yml` could easily assume `docker-compose up` gives them a working local chain — it does not.
- **The optional background worker `backend/app/workers/anchor_confirmer.py`** is deliberately excluded from the coverage gate (`pyproject.toml`'s `omit = ["app/workers/*"]`) and, per `docs/TEST_PLAN.md`, not directly tested — justified as the documented "safe to leave untested first" cut-list item, since the synchronous confirm-on-approve path it duplicates *is* fully tested. Still: this is the one production code path with zero direct test coverage.
- **ClamAV / malware scanning is explicitly not implemented** (per `docs/THREAT_MODEL.md` reference in `docs/TEST_PLAN.md:90`) — uploaded files are validated for size/MIME only, not scanned for malicious content.
- **No end-to-end browser automation** (Playwright) and **no load/performance testing** (locust/k6) — both explicitly deferred as "Level-3/optional" per the project plan, exercised manually via `docs/DEMO_SCRIPT.md` instead.
- No `TODO`/`FIXME`/`XXX`/`HACK`/"not implemented" markers were found anywhere in `backend/app`, `frontend/src`, or `contracts/contracts` except one benign in-code comment in `backend/app/services/storage.py:14` referencing a hypothetical `NotImplemented: KMS not configured` MinIO error string (not an actual stub in this codebase — it's describing MinIO's own error text for context).
- Rate limiting for login attempts is an **explicit in-memory per-process stub** (`backend/app/modules/auth/service.py`, module docstring: "fine for the single-instance prototype target; a distributed deployment would need a shared store like Redis instead") — this will not work correctly if the backend is ever horizontally scaled (each process has its own counter, and a restart clears all counters).
- MongoDB Atlas network access in production may default to `0.0.0.0/0` per `docs/DEPLOYMENT.md:53-54` because Render's free-tier outbound IPs aren't static — flagged in the docs themselves as "a known trade-off, not an oversight," but still worth knowing before treating this as a hardened production system.

### Bugs / code smells noticed while reading

- `backend/app/modules/documents/service.py:210-213` — in `list_documents`, an invalid `owner_id` string silently falls back to `ObjectId()` (a fresh random id "guaranteed no match") rather than raising a 400. This is intentional (comment says so) but means a client typo in a query param produces an empty result set with no error signal, which could be confusing during debugging/QA rather than a real bug.
- `backend/app/modules/documents/workflow.py:109` has a `# pragma: no cover` branch for an "unknown review decision" that the `Literal` type on the schema is expected to reject before ever reaching the service — reasonable but means that defensive code path is genuinely unverified by tests (acceptable given the type-level guarantee, but worth knowing if the schema's `Literal` type is ever loosened).
- `.ruff_cache` and `backend/.ruff_cache`, `backend/.pytest_cache`, `backend/.venv`, `frontend/node_modules`, `frontend/dist`, `contracts/node_modules`, `contracts/artifacts`, `contracts/typechain-types` are all present in the working tree as build/cache artifacts (likely `.gitignore`'d, not necessarily committed — worth confirming `git status` is clean of these if you didn't intend them tracked).
- Two "React bugs" caught by ESLint are mentioned in the Phase 11 commit message (`34bec7e Phase 11: ... ESLint (caught 2 React bugs)`) but not detailed anywhere in-repo — the fixes are presumably already applied (this is a historical note, not a current issue), but there's no changelog identifying exactly what they were, so a future contributor can't learn from that history.

### Test coverage summary

Per `docs/TEST_PLAN.md` (current as of Phase 12) and confirmed against actual test file listing:

- **Backend**: 118 tests (docs say "114" in the git log Phase 11 message, "118" in the up-to-date TEST_PLAN.md and README — the number grew between phases; treat 118 as current), **92.4% line coverage**, gate enforced at 60% via `pyproject.toml`. Structure: `tests/unit/` (hashing, geofence math, `require_geofence` dependency, security/JWT primitives), `tests/api/` (auth, users, RBAC, full authz matrix, geofences, reports, audit, security edge cases like IDOR/NoSQL-injection-shaped payloads, hardening/rate-limit/security-headers), `tests/integration/` (upload, full workflow incl. anchoring against a **real local Hardhat node**, verify VERIFIED/MISMATCH/NOT_ANCHORED, archival).
- **Contracts**: Hardhat/Mocha suite (95 lines, `contracts/test/DocumentAnchor.test.ts`) covering `anchor()`, re-anchor-reverts, `onlyWriter` modifier, `getAnchor()` read, owner-only `setWriter()`.
- **Frontend**: Vitest — `frontend/src/pages/__tests__/Login.test.tsx`, `Verification.test.tsx` (green/red result rendering), `frontend/src/components/__tests__/FileDropzone.test.tsx` (rejects disallowed files pre-submit). This is a thin slice of the frontend (3 test files vs. ~35 source files) — most pages (Dashboard, DocumentRepository, DocumentDetails, VersionHistory, AmendmentRequest, BlockchainVerification, GeofenceStatus, AuditLogs, AdminPanel, Settings) have **no automated test coverage** at all.
- Explicitly **not covered anywhere**: load/perf testing, E2E browser automation, the background anchor-confirmer worker, malware scanning (not implemented so nothing to test).

---

## 5. MANUAL TESTING GUIDE

**Prerequisites for all flows**: `docker-compose up` (Mongo + MinIO + placeholder chain + backend running), frontend running via `cd frontend && npm run dev`, and `python scripts/seed.py --demo` run once to create the 5 demo users + HQ geofence. For anchoring-dependent flows, `.env` needs real `SEPOLIA_RPC_URL`/`SERVICE_WALLET_PRIVATE_KEY`/`CONTRACT_ADDRESS` (deployed via `npx hardhat run scripts/deploy.ts --network sepolia`) and a funded service wallet — without this, documents will get stuck at `APPROVED` (anchor pending) rather than reaching `ACTIVE`.

### 5.1 Health check
```bash
curl http://localhost:8000/api/v1/health
```
Expected: `{"status":"ok"|"degraded", "mongo":"reachable", "storage":"reachable", "chain":"reachable"|"degraded"}`. `chain: degraded` is expected/normal unless Sepolia config is real.

### 5.2 Login / auth
1. Open http://localhost:5173/login.
2. Log in as `legal_officer@geolegalvault.demo` / `Demo@Pass123!`.
   - Expected: redirected to Dashboard; JWT stored (check `frontend/src/lib/authToken.ts` storage location); nav shows only permissions the Legal Officer role has (Upload, Documents, Verify, Amend, Archive — not Admin or Audit).
3. Log out, then attempt to visit `/admin` directly while logged out.
   - Expected: redirected to `/login` (ProtectedRoute).
4. Log in as `auditor@geolegalvault.demo`, visit `/admin`.
   - Expected: 403 → routed to `/forbidden` page (Auditor lacks `USERS_MANAGE`).
5. API-level: `curl -X POST http://localhost:8000/api/v1/auth/refresh` twice with the **same** refresh token.
   - Expected: first call succeeds (200, new token pair); second call with the now-stale token returns 401 and (per `auth/service.py`) revokes the whole session family — confirm by trying the *first* refreshed token afterward too; it should also now fail.
6. Attempt 6 rapid failed logins with a wrong password for the same email within 60s.
   - Expected: 5th/6th attempt returns a rate-limited response (`RateLimited`), per `_MAX_ATTEMPTS = 5` / `_WINDOW_SEC = 60.0` in `auth/service.py`.

### 5.3 Geofence enforcement
Prerequisite: `--demo` seed creates an "HQ Campus (demo)" geofence around `lat 11.66-11.68, lng 78.14-78.16` (see `scripts/seed.py:48-57`), with `HQ_INSIDE_POINT = {11.67, 78.15}` and `HQ_OUTSIDE_POINT = {11.00, 77.00}`.
1. As `authorized_staff@geolegalvault.demo`, go to `/documents/upload`.
2. Use browser DevTools sensors (or the app's LocationGate mock, if present) to simulate the **outside** point, then attempt to upload.
   - Expected: 403 `GEOFENCE_DENIED`; check `/audit` (as Auditor) afterward — a `GEOFENCE_DENIED` entry should appear for that user.
3. Simulate the **inside** point, retry the upload.
   - Expected: succeeds, document created in `DRAFT`.
4. Try an accuracy value > 100m (`GEO_ACCURACY_MAX_M` default) at the inside coordinates.
   - Expected: 422 `LOCATION_LOW_CONFIDENCE`.
5. Try a `timestamp` more than 60s old (`GEO_FRESHNESS_MAX_SEC` default).
   - Expected: 422 `LOCATION_STALE`.

### 5.4 Upload validation
1. Upload a `.pdf` under 10MB (`MAX_UPLOAD_MB`) with correct `Content-Type: application/pdf`.
   - Expected: 201, document + V1 in `DRAFT`, SHA-256 hash visible in Document Details.
2. Upload an 11MB+ file.
   - Expected: 413 `FILE_TOO_LARGE`.
3. Upload a file whose extension/claimed content-type says `.pdf` but whose actual bytes are e.g. a renamed `.exe` or plain text.
   - Expected: 422 `MIME_MISMATCH`.
4. Upload with a malicious filename (`../../etc/passwd`, or `<script>.pdf`).
   - Expected: succeeds if content is valid (filename is never used as the storage key — verify in MinIO console at :9001 that the stored object key is a generated path like `documents/<id>/v1`, not the literal filename).

### 5.5 Full lifecycle (maker-checker + anchoring)
1. As `authorized_staff` (or `legal_officer`), upload → note document id → `submit()` it (DRAFT→SUBMITTED).
2. Log in as `reviewing_officer`, go to the document, choose "Review → Approve" (not "Changes Requested").
   - Expected: SUBMITTED→UNDER_REVIEW→PENDING_APPROVAL in one call. Try reviewing your **own** upload if you're also the reviewer (same user) — expected 403 `MAKER_CHECKER_VIOLATION`.
3. Log in as `legal_officer` (different from uploader), approve the document.
   - Expected: 200; response includes an `anchor` object. If Sepolia config is real: status trends APPROVED→BLOCKCHAIN_ANCHORED→ACTIVE within the poll window (a few seconds); check the returned `tx_hash` on https://sepolia.etherscan.io/tx/<hash>. If Sepolia config is placeholder: document stays `APPROVED`, `anchor.status != "PENDING"`, and `anchor_pending_alert=true` on the document — this is expected, not a bug.
4. Try approving the **same document twice**, or approving a document still in `DRAFT`.
   - Expected: 409 `ILLEGAL_TRANSITION`.
5. Request an amendment on the now-`ACTIVE` document (as `legal_officer` or `authorized_staff`), then upload a new version.
   - Expected: ACTIVE→AMENDMENT_REQUESTED→(new V2 in DRAFT); repeat submit/review/approve for V2; once V2 reaches ACTIVE, V1 should show as `SUPERSEDED` in Version History but remain downloadable/verifiable — confirm its bytes/hash are unchanged.
6. Archive the ACTIVE document as `legal_officer` or `administrator`.
   - Expected: disappears from the default `/documents` list but is still retrievable when explicitly filtering `status=ARCHIVED`; its versions/anchors remain intact.

### 5.6 Verification (3-way tamper detection)
1. On an anchored (`ACTIVE`) version, go to `/verify/:versionId` (needs `VERIFY_PERFORM` — most roles have it).
   - Expected: green `VERIFIED` badge; recomputed/stored/on-chain hashes shown as matching.
2. Simulate tampering: overwrite the object directly in MinIO (console :9001, browse to the bucket/key from Document Details) with different bytes, then re-run Verify.
   - Expected: red `MISMATCH`; document's `integrity_flag` becomes `TAMPERED` (check via `/documents/:id` or DB); an audit `VERIFY_FAIL` entry is recorded.
3. Verify a version that was never approved/anchored (still in DRAFT).
   - Expected: grey `NOT_ANCHORED` — not treated as an error.
4. (Advanced/DB-level) Manually edit the `document_versions.sha256` field in Mongo to match a tampered file, then verify again.
   - Expected: still `MISMATCH`, because the on-chain hash (independent ground truth) won't match either — this is the core "even a DB compromise can't fake a pass" guarantee; confirm it holds.

### 5.7 Audit log
1. As `auditor@geolegalvault.demo`, visit `/audit`.
   - Expected: chronological list of actions across all the above steps (LOGIN_SUCCESS/FAILURE, SUBMIT, REVIEW_START/PASS, APPROVE, ANCHOR_OK/FAIL, ACTIVATE, VERIFY_PASS/FAIL/NOT_ANCHORED, GEOFENCE_DENIED, ARCHIVE, AMEND_REQ, etc.).
2. As `legal_officer` (no `AUDIT_VIEW` permission), attempt `GET /api/v1/audit` directly via curl with that user's token.
   - Expected: 403.
3. Attempt any `PUT`/`PATCH`/`DELETE` against `/api/v1/audit/*`.
   - Expected: 404/405 — no such route exists (append-only by omission).

### 5.8 Admin / reports
1. As `administrator@geolegalvault.demo`, visit `/admin`.
   - Expected: User Management panel (create/deactivate users, assign roles/geofences), Geofence Management panel (CRUD polygons), Reports panel, Health panel.
2. Check `/admin` Reports panel against `GET /api/v1/reports/summary`.
   - Expected: counts by document status/doc_type, anchoring pending/confirmed/failed + success rate, recent (30-day window) verification VERIFIED/MISMATCH/NOT_ANCHORED counts, `geofence_denied_count` — cross-check these against the actions you performed in the steps above.
3. Try creating/approving a document as `administrator`.
   - Expected: 403 — Administrator role deliberately has no `DOCUMENT_UPLOAD`/`APPROVE_PERFORM` permission (separation of duties, `core/rbac.py:24-38`).

### 5.9 Demo document corpus (optional, for a fuller QA pass)
```bash
python scripts/seed.py --seed-documents --count 40
```
Requires `--demo` already run and (for meaningful amendment/tamper cases) real Sepolia config. Produces ~30-50 documents spread across lifecycle states, some with a real V1→V2 amendment, and 5 pre-tampered so `/documents` and Verify have ready-made MISMATCH cases without you manually corrupting MinIO objects.

---

## 6. NEXT STEPS / IMPROVEMENT OPPORTUNITIES

### Code quality / architecture
- **Populate `CLAUDE.md`** — it's referenced from `README.md` as the canonical guardrails document but is currently empty; either restore its content (the guardrails clearly exist conceptually, referenced throughout code comments as "Guardrail #1" through "#7") or update `README.md` to stop pointing at it.
- **Replace the in-memory login rate limiter** (`auth/service.py`) with a shared store (Redis) before any horizontal scaling — currently documented as a known prototype limitation, but it's the kind of thing that's easy to forget until a real incident.
- **Investigate `scripts/faucet_check.py`** (1 line) — confirm whether it's a genuine stub that needs finishing, or dead code that should be removed; either way it's inconsistent with the otherwise-thorough `scripts/` directory.
- **Consider adding schema-level idempotency protection** around `documents/workflow.py::approve()`'s anchor retry loop — currently a transient failure inside the loop leaves `anchor_pending_alert=True`, but there's no automatic backoff/re-trigger without either the optional worker running or a manual re-approve-like action; worth confirming the worker (`workers/anchor_confirmer.py`) is actually deployed in production (it's optional and untested).
- **Tighten `list_documents`' `owner_id` fallback** (`documents/service.py:210-213`) — silently mapping an invalid id to "no results" is convenient internally but could hide client bugs; consider a 400 for a malformed `owner_id` query param instead.

### Feature extensions (logical next steps given the current design)
- **Malware scanning** (ClamAV or similar) before storage — currently the single largest gap flagged in the project's own threat model.
- **Multi-signature or role-diverse anchoring** — right now one service wallet signs every anchor tx; for a real deployment beyond a prototype, consider a multi-sig or at least key-rotation story for `SERVICE_WALLET_PRIVATE_KEY`.
- **Playwright E2E suite** — the manual `DEMO_SCRIPT.md` walkthrough is a reasonable stopgap, but an automated E2E suite covering the golden path (upload→approve→anchor→verify) would catch regressions CI currently can't.
- **Frontend test coverage** — only 3 of ~35 frontend source files have tests; the highest-value additions would be `DocumentDetails`, `VersionHistory`, and `AdminPanel` since those exercise the most RBAC/permission-branching logic.
- **Notification/alerting on `anchor_pending_alert`** — the flag exists and is surfaced in the DB/API, but confirm the frontend actually renders a persistent, visible warning for it (worth a manual test pass) rather than only showing up in the Reports aggregation.

### Technical debt worth prioritizing (rough order)
1. Empty `CLAUDE.md` / dangling guardrails reference — cheap fix, currently misleading.
2. In-memory rate limiter — low cost now, becomes a real bug the day this scales past one process.
3. Missing malware scanning — explicitly the biggest security gap the project's own `THREAT_MODEL.md` names.
4. Thin frontend test coverage relative to backend's 92% — asymmetry that will make frontend regressions the most likely source of undetected bugs going forward.
5. `scripts/faucet_check.py` stub — low priority but worth a 5-minute look so it's not a landmine for the next person following the deployment docs.
