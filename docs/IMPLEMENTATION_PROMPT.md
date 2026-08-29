# GeoLegalVault — Phase-Wise Implementation Prompt (for Claude in VS Code)

> **Purpose:** This document is the build script for GeoLegalVault. Give it to Claude Code in VS Code **one phase at a time**. Each phase has a copy-paste **`PROMPT ►`** block, an explicit **file list**, and a **DoD (Definition of Done)** gate you must pass before moving on.
> **Authority:** This document strictly implements `GeoLegalVault_Project_Plan.md`. Where this doc references "Part N," it means that part of the plan. **If anything here conflicts with the plan, the plan wins — stop and ask.**

---

## HOW TO USE THIS DOCUMENT

1. Keep both files in the repo: `docs/GeoLegalVault_Project_Plan.md` (the plan) and `docs/IMPLEMENTATION_PROMPT.md` (this file).
2. For each phase, **paste the `PROMPT ►` block into Claude Code.** Also tell it: *"Follow docs/GeoLegalVault_Project_Plan.md and docs/IMPLEMENTATION_PROMPT.md. Do only this phase. Stop at the DoD checklist and report."*
3. After Claude finishes a phase, run the **Verify** commands. Do not start the next phase until every DoD box is checked.
4. Phases are ordered by dependency. **Do not reorder.** The tamper-detection loop (Phase 6) is the product's core — everything builds toward it.

---

## MASTER GUARDRAILS (apply to EVERY phase — never violate)

Paste this block once at the start of every Claude Code session:

```
GLOBAL RULES FOR THIS PROJECT (never break, in any phase):
1. DOCUMENTS STAY OFF-CHAIN. Only anchor {documentId, version, sha256 hash, eventType, timestamp} on Ethereum Sepolia. Never put file bytes, names, or PII on-chain.
2. NO SECRETS IN GIT. Private keys, RPC URLs with keys, DB URIs, R2 keys, JWT secrets live only in .env (gitignored) / platform env. Commit only .env.example with placeholder values. Add secret patterns to .gitignore.
3. BACKEND SERVICE-WALLET SIGNS ANCHORS. Do NOT use per-user MetaMask. The backend holds ONE service wallet key (env var) and signs anchoring txns. Anchoring is an automatic system event on APPROVAL, never a user action.
4. STORAGE IS CLOUDFLARE R2 (S3-compatible), private bucket, access only via short-lived pre-signed URLs. Do NOT make buckets public. Do NOT proxy large files through the API.
5. ENFORCEMENT PIPELINE, in this exact order, on every sensitive op: TLS -> JWT verify -> RBAC (deny-by-default) -> server-side geofence check -> input/file validation -> action -> audit log. The geofence check is ALWAYS server-side; NEVER trust a client "allowed=true" flag.
6. GEOFENCE IS POLICY, NOT A SECURITY GUARANTEE. Browser GPS is spoofable. No code comments, docs, UI text, or logs may claim "military-grade", "tamper-proof", "unhackable", or "guaranteed location". Use "tamper-evident", "detects modification", "policy-level geofencing", "prototype".
7. VERSIONS ARE IMMUTABLE. document_versions is insert-only. Amendment creates V(n+1) with prev_version_hash pointing to V(n)'s hash. NEVER overwrite or mutate an existing version's content/hash. Only a whitelisted status field may change.
8. DO NOT BUILD (out of scope): Merkle/hierarchical hashing, NLP, microservices/message brokers, mainnet, on-chain storage, multi-tenant billing, contract upgradeability proxies, real GPS hardware attestation. (These belong to TARP or are unnecessary.)
9. GEOJSON IS [longitude, latitude] ORDER. Validate coordinate order on every input. This is the #1 geofence bug.
10. MODULAR MONOLITH. One FastAPI app, organized by module. No separate services/queues except ONE optional background worker for blockchain confirmation polling.
11. TESTS ARE NOT OPTIONAL for core services (hashing, geofence, RBAC, state machine, contract). Write them in the same phase as the code.
12. When unsure about a design decision, re-read the relevant Part of the plan and follow it. Do not invent scope.
```

---

## LOCKED REFERENCE (condensed — full detail in the plan)

**Architecture:** React SPA (Vercel) → FastAPI modular monolith (Render) {Auth, RBAC, Geofence, Document, Hashing, Version, Audit, Blockchain} → MongoDB Atlas (metadata, geofences w/ 2dsphere, audit, anchors, verifications) + Cloudflare R2 (encrypted blobs) + Sepolia (`DocumentAnchor`) + optional confirmation worker.

**Stack:** React+Vite+TypeScript+Tailwind+TanStack Query · FastAPI+Python+Pydantic · JWT(PyJWT)+Argon2id · MongoDB(2dsphere) · Cloudflare R2 · Solidity+Hardhat+web3.py+Sepolia(Alchemy RPC) · Docker+compose · GitHub Actions · Sentry · Vercel+Render. **Cost target: ₹0.**

**Roles (Part 3):** Administrator, Legal Officer, Reviewing Officer, Authorized Staff, Auditor. Deny-by-default. Maker≠checker (approver ≠ uploader).

**Lifecycle states (Part 5):** DRAFT → SUBMITTED → UNDER_REVIEW → PENDING_APPROVAL → APPROVED → BLOCKCHAIN_ANCHORED → ACTIVE → (AMENDMENT_REQUESTED → new DRAFT V(n+1)) ; ACTIVE/SUPERSEDED → ARCHIVED. CHANGES_REQUESTED loops back to DRAFT.

**Collections (Part 10):** users, documents, document_versions(immutable), geofences(2dsphere), permissions(opt), audit_logs(append-only), blockchain_anchors, verification_records.

**Contract (Part 12):** `DocumentAnchor.anchor(documentId, version, hash, eventType)` (onlyWriter, reject re-anchor of same doc+version), `getAnchor(...)`, event `AnchorCreated`.

**Environment variables (single source of truth — `.env.example`):**
```
# --- Backend ---
APP_ENV=development
JWT_SECRET=change_me
JWT_ACCESS_TTL_MIN=15
JWT_REFRESH_TTL_DAYS=7
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=geolegalvault
# --- Storage (R2 / S3-compatible; MinIO for local dev) ---
STORAGE_ENDPOINT=http://localhost:9000
STORAGE_REGION=auto
STORAGE_BUCKET=geolegalvault-dev
STORAGE_ACCESS_KEY=change_me
STORAGE_SECRET_KEY=change_me
STORAGE_PRESIGN_TTL_SEC=60
MAX_UPLOAD_MB=10
# --- Blockchain ---
SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/CHANGE_ME
SERVICE_WALLET_PRIVATE_KEY=change_me      # NEVER commit a real key
CONTRACT_ADDRESS=0xCHANGE_ME
CHAIN_ID=11155111
ANCHOR_CONFIRMATIONS=1
# --- Geofence ---
GEO_ACCURACY_MAX_M=100
GEO_FRESHNESS_MAX_SEC=60
# --- Observability ---
SENTRY_DSN=
# --- Frontend (frontend/.env) ---
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

---

## TARGET REPOSITORY STRUCTURE (Part 19 — create in Phase 0)

```
geolegalvault/
├── frontend/
│   ├── src/{pages,components,api,hooks,lib,context}/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── .env.example
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/            # config, security, db, deps, logging, errors
│   │   ├── modules/{auth,users,documents,versions,geofences,audit,blockchain,verify,reports}/
│   │   │                    # each: router.py, service.py, schemas.py, models.py
│   │   ├── services/        # hashing.py, storage.py, blockchain.py, geofence.py
│   │   ├── models/          # shared pydantic + mongo helpers
│   │   └── workers/         # anchor_confirmer.py (optional)
│   ├── tests/{unit,integration,api}/
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── Dockerfile
├── contracts/
│   ├── contracts/DocumentAnchor.sol
│   ├── scripts/deploy.ts
│   ├── test/DocumentAnchor.test.ts
│   └── hardhat.config.ts
├── docs/                    # plan, this prompt, SRS, threat model, API, DB, test plan, deploy, guides, research, demo script
├── scripts/                 # seed.py, backup.sh, faucet_check.py
├── .github/workflows/ci.yml
├── docker-compose.yml       # mongo + minio + hardhat-node + backend
├── .env.example
├── .gitignore
└── README.md
```

---

## PHASE MAP (dependency-ordered)

| Phase | Title | Plan parts | Builds toward |
|---|---|---|---|
| 0 | Scaffolding, env, docker-compose, health | 19, 23, F | working skeleton |
| 1 | Auth (JWT, Argon2id, refresh) + Users | 2(FR1-3), 15 | identity gate |
| 2 | RBAC (deny-by-default, role matrix) | 3, 14 | role gate |
| 3 | Geofences (2dsphere CRUD + server-side enforcement) | 10, 11 | location gate |
| 4 | Storage + Hashing + Documents + immutable Versions | 8-10, 13, 17 | upload→hash→store |
| 5 | Smart contract + deploy Sepolia + anchor service | 12, 18 | on-chain anchor |
| 6 | Lifecycle workflow (state machine, review/approve/amend, anchoring) | 5, 4, 17 | approved→anchored→active |
| 7 | **Verification loop (3-way, tamper detection)** ★core | 6(S5), 13, 17 | VERIFIED / MISMATCH |
| 8 | Audit logging + observability | 20, 32 | oversight |
| 9 | Frontend (all core pages) | 16 | usable UI |
| 10 | Admin, users mgmt, reporting, archival | 2, 3, 16 | Level-2 |
| 11 | Testing suite + CI | 20, 19 | quality gate |
| 12 | Deployment (Vercel/Render/Atlas/R2/Sepolia) + docs + demo | 30-34, 33 | ship + demo |
| 13 | Optional Level-3 (only if ahead) | 26(L3) | polish |

Phases 0–7 = the MVP loop (must reach by Week 5, Part 24). Phases 8–12 = harden/UI/ship. Phase 13 = only if time remains.

---

## PHASE 0 — Scaffolding, Environment, Health

**Goal:** One-command local dev environment; empty-but-running FastAPI + React + Mongo connection + health check. (Plan Parts 19, 23, First-7-Days Day 1–2.)

**Depends on:** nothing.

**Deliverables (files):** full repo tree above (empty module stubs OK), `docker-compose.yml`, `.env.example`, `frontend/.env.example`, `.gitignore`, `README.md`, `backend/app/main.py` with `/api/v1/health`, `backend/app/core/{config.py,db.py,logging.py}`, `backend/Dockerfile`, `backend/requirements.txt`, `frontend` Vite+TS+Tailwind skeleton.

**PROMPT ►**
```
Implement PHASE 0 of docs/IMPLEMENTATION_PROMPT.md, following docs/GeoLegalVault_Project_Plan.md. Do ONLY this phase.

Create the full monorepo structure exactly as in "TARGET REPOSITORY STRUCTURE" (create empty stub files/dirs for later phases so the tree exists).

Backend (Python 3.11+, FastAPI):
- backend/app/main.py: FastAPI app, CORS for the frontend origin, /api/v1/health returning {status, mongo, storage, chain} where each dependency check is a simple reachability probe (mongo ping; storage/chain may return "not_configured" for now).
- backend/app/core/config.py: pydantic-settings Settings loading all env vars from the .env.example list. Fail fast on missing required vars in non-dev.
- backend/app/core/db.py: Motor (async MongoDB) client + get_db() dependency + a startup hook that ensures indexes (empty for now, extend later).
- backend/app/core/logging.py: structured JSON logging middleware (request id, method, path, status, duration_ms).
- backend/requirements.txt + pyproject.toml: fastapi, uvicorn, motor, pydantic, pydantic-settings, python-jose or pyjwt, argon2-cffi/passlib[argon2], boto3, web3, python-magic, pytest, httpx, ruff.
- backend/Dockerfile: slim python image, run uvicorn.

Frontend (Vite + React + TypeScript + Tailwind + React Router + TanStack Query):
- Minimal app with a placeholder page that calls /api/v1/health and shows the JSON. Configure VITE_API_BASE_URL from env.

Root:
- docker-compose.yml: services = mongo (mongo:7), minio (S3-compatible, console+api ports, create bucket via a one-shot init), hardhat-node (placeholder service or documented as added in Phase 5), backend (build ./backend, depends_on mongo+minio, env_file .env). Do NOT put real secrets in compose.
- .env.example (root) and frontend/.env.example exactly matching the env var list in the prompt doc.
- .gitignore: .env, .env.*, !*.example, __pycache__, node_modules, dist, .venv, *.key, artifacts/, cache/, coverage.
- README.md: prerequisites, "docker-compose up", how to run backend + frontend locally, env setup steps.

STOP after producing the PHASE 0 DoD checklist with each item marked done/not-done and any manual steps I must do (e.g., create .env from .env.example).
```

**DoD:**
- [ ] `docker-compose up` starts mongo + minio + backend without errors.
- [ ] `GET /api/v1/health` returns 200 with mongo reachable.
- [ ] Frontend dev server runs and displays the health JSON.
- [ ] `.env` is gitignored; only `.env.example` is committed; no secrets in repo.
- [ ] Repo tree matches the target structure (stubs allowed).

**Verify:** `docker-compose up -d && curl -s localhost:8000/api/v1/health | jq` ; `git status` shows no `.env`; `cd frontend && npm run dev`.

---

## PHASE 1 — Authentication + Users

**Goal:** JWT auth (short access + refresh rotation), Argon2id password hashing, admin-provisioned users. (Parts 2 FR1–3, FR2, 15.)

**Depends on:** Phase 0.

**Deliverables:** `backend/app/core/security.py` (hashing, token create/verify), `backend/app/modules/auth/{router,service,schemas}.py`, `backend/app/modules/users/{router,service,schemas,models}.py`, `backend/app/core/deps.py` (`get_current_user`), tests in `tests/unit/test_security.py`, `tests/api/test_auth.py`.

**PROMPT ►**
```
Implement PHASE 1 (Auth + Users) per docs/IMPLEMENTATION_PROMPT.md and Plan Parts 2, 15. Do ONLY this phase. Obey MASTER GUARDRAILS (esp. #2 no secrets, #7 immutability n/a here).

security.py:
- Password hashing with Argon2id (argon2-cffi). hash_password / verify_password, constant-time.
- JWT: create_access_token (TTL from JWT_ACCESS_TTL_MIN, claims sub, role, iat, exp, jti), create_refresh_token (TTL JWT_REFRESH_TTL_DAYS), verify_token pinning the algorithm (HS256) and rejecting alg=none.

users module:
- Mongo `users` collection: {_id, email(unique), password_hash, name, role, assigned_geofence_ids[], is_active, created_at, last_login}. Ensure unique index on email.
- Admin-only endpoints: POST /users (create), GET /users (list, paginated), PATCH /users/{id} (update/deactivate). Never hard-delete a user; deactivate via is_active. Never return password_hash.
- Roles enum: ADMINISTRATOR, LEGAL_OFFICER, REVIEWING_OFFICER, AUTHORIZED_STAFF, AUDITOR.

auth module:
- POST /auth/login: verify credentials, return access token (JSON) + set refresh token as httpOnly, Secure, SameSite=strict cookie. Generic error on failure (no user enumeration). Rate-limit hook (stub or slowapi).
- POST /auth/refresh: rotate refresh token; detect reuse of an old token and revoke the session family (store refresh jti + family in a refresh_sessions collection).
- POST /auth/logout: revoke current session.
- deps.get_current_user: extract+verify access token, load user, reject if inactive.

Seed helper: add a create-admin function usable from scripts/seed.py.

Tests: hashing round-trip; token expiry + tampered token rejected + alg=none rejected; login success/failure; refresh rotation + reuse-revocation; protected route requires valid token.

STOP at the PHASE 1 DoD checklist.
```

**DoD:**
- [ ] Argon2id hashing works; wrong password fails; no plaintext stored.
- [ ] Login returns access token + httpOnly refresh cookie; invalid creds → 401 generic.
- [ ] Access token expires per TTL; tampered/`none`-alg tokens rejected.
- [ ] Refresh rotation works; reused refresh token revokes the session family.
- [ ] Admin can create/list/deactivate users; `password_hash` never returned; email unique.
- [ ] Tests pass (`pytest tests/unit tests/api -k auth`).

**Verify:** `pytest -k "auth or security"` ; manual: login → call a protected route with/without token.

---

## PHASE 2 — RBAC (Deny-by-Default)

**Goal:** Central role→permission enforcement on every protected endpoint; maker≠checker rule available. (Parts 3, 14.)

**Depends on:** Phase 1.

**Deliverables:** `backend/app/core/rbac.py` (permission map + `require(permission)` dependency), permission constants, tests `tests/api/test_rbac.py`.

**PROMPT ►**
```
Implement PHASE 2 (RBAC) per Plan Part 3 (permission matrix) and Part 14. Do ONLY this phase.

rbac.py:
- Permission strings, e.g. document:upload, document:view, document:search, document:amend, review:perform, approve:perform, verify:perform, users:manage, geofence:manage, audit:view, document:archive.
- ROLE_PERMISSIONS map implementing EXACTLY the Part 3 matrix:
  ADMINISTRATOR: view, search, verify, users:manage, geofence:manage, audit:view, document:archive (NOT upload/approve/review — separation of duties).
  LEGAL_OFFICER: upload, view, search, amend, approve, verify (triggers anchoring).
  REVIEWING_OFFICER: view, search, review, verify.
  AUTHORIZED_STAFF: upload, view, search, amend, verify.
  AUDITOR: view(read-only), search, verify, audit:view. Read-only everywhere; cannot mutate.
- require(permission): FastAPI dependency, deny-by-default; missing permission -> 403 with {error:{code:"FORBIDDEN"}}. Derive role from the DB user (not blindly from token) for sensitive ops.
- helper enforce_maker_checker(uploader_id, actor_id) that raises 403 if approver == uploader.

Apply require(...) to existing user endpoints. Add an authz test that iterates every role against a sample of endpoints and asserts allow/deny matches the matrix.

STOP at the PHASE 2 DoD checklist.
```

**DoD:**
- [ ] Every protected endpoint declares a required permission; unlisted = denied.
- [ ] Role→permission map matches Part 3 exactly (incl. Admin cannot approve; Auditor read-only).
- [ ] `enforce_maker_checker` blocks approver == uploader.
- [ ] Authz matrix test passes for all roles.

**Verify:** `pytest -k rbac` ; manual: call an Admin-only route as Auditor → 403.

---

## PHASE 3 — Geofences (2dsphere + Server-Side Enforcement)

**Goal:** Admin CRUD for GeoJSON geofences; server-side point-in-polygon check with accuracy/freshness fail-closed. (Parts 10, 11.)

**Depends on:** Phases 1–2.

**Deliverables:** `backend/app/modules/geofences/{router,service,schemas,models}.py`, `backend/app/services/geofence.py` (check logic), 2dsphere index creation, tests `tests/unit/test_geofence.py`.

**PROMPT ►**
```
Implement PHASE 3 (Geofences) per Plan Parts 10 and 11. Do ONLY this phase. Obey GUARDRAIL #5 (server-side only) and #9 (GeoJSON is [lng,lat]).

geofences collection: {_id, name, region(GeoJSON Polygon), radius_m?, center(GeoJSON Point)?, active, created_at}. Create a 2dsphere index on region (and on center if used). Validate on input: valid GeoJSON, closed polygon ring, plausible coordinate ranges (lng -180..180, lat -90..90), vertex cap (e.g. <=100), reject swapped lat/lng via range check.

Admin-only endpoints (require geofence:manage): POST /geofences, GET /geofences, GET /geofences/{id}, PATCH /geofences/{id} (edit/deactivate). Do not hard-delete a fence in use; deactivate.

services/geofence.py -> check_location(user, lat, lng, accuracy_m, client_ts):
  1. if accuracy_m > GEO_ACCURACY_MAX_M: raise 422 LOCATION_LOW_CONFIDENCE (fail-closed).
  2. if now - client_ts > GEO_FRESHNESS_MAX_SEC: raise 422 LOCATION_STALE.
  3. query geofences where _id in user.assigned_geofence_ids AND active AND region $geoIntersects Point[lng,lat].
  4. if none: raise 403 GEOFENCE_DENIED (audit later). else return the matching fence.
Never trust any client-provided "inside/allowed" value; always run the DB query.

Add a reusable FastAPI dependency require_geofence(permission_context) that reads {lat,lng,accuracy,timestamp} from the request (body/header) and calls check_location. This dependency will guard upload/download/approve/amend in later phases.

Tests (use a known polygon): point clearly inside -> pass; clearly outside -> 403; on-edge -> deterministic result; accuracy 500m -> 422; stale timestamp -> 422; swapped lat/lng input -> validation error.

STOP at the PHASE 3 DoD checklist.
```

**DoD:**
- [ ] Geofence CRUD works; 2dsphere index exists (`db.geofences.getIndexes()`).
- [ ] `$geoIntersects` point-in-polygon returns correct inside/outside/edge results.
- [ ] Accuracy > max → 422; stale timestamp → 422; outside → 403 (all fail-closed).
- [ ] Coordinate order/range validated; swapped lat/lng rejected.
- [ ] `require_geofence` dependency is reusable and server-side only.
- [ ] Tests pass.

**Verify:** `pytest -k geofence` ; manual: create HQ polygon, test an inside and an outside point.

---

## PHASE 4 — Storage + Hashing + Documents + Immutable Versions

**Goal:** Validated encrypted upload to R2/MinIO, SHA-256 fingerprint, `documents` + insert-only `document_versions` with prev-hash chain, pre-signed download. (Parts 8–10, 13, 17.)

**Depends on:** Phases 1–3.

**Deliverables:** `backend/app/services/storage.py`, `backend/app/services/hashing.py`, `backend/app/modules/documents/{router,service,schemas,models}.py`, `backend/app/modules/versions/{router,service,models}.py`, tests `tests/unit/test_hashing.py`, `tests/integration/test_upload.py`.

**PROMPT ►**
```
Implement PHASE 4 (Storage + Hashing + Documents + Versions) per Plan Parts 8-10, 13, 17. Do ONLY this phase. Obey GUARDRAILS #1 (off-chain), #4 (private R2, pre-signed), #7 (versions immutable), #5 (pipeline order).

services/storage.py (boto3 against R2/MinIO via STORAGE_* env):
- put_object(bytes, key) with server-side encryption; keys are server-generated: docs/{document_id}/v{n}. Never use client filename as the key (prevents path traversal).
- generate_presigned_get(key, ttl=STORAGE_PRESIGN_TTL_SEC).
- Bucket is private; enforce no public ACL.

services/hashing.py:
- sha256_bytes(data) -> hex. Stream-friendly for up to MAX_UPLOAD_MB.

documents module:
- documents collection: {_id, title, doc_type, classification, owner_id, status, current_version_id, tags[], created_at, updated_at, retention_until}. Indexes: status, owner_id, text index on title+tags, compound {status, doc_type}.
- document_versions collection (INSERT-ONLY): {_id, document_id, version_no, sha256, prev_version_hash, storage_key, size_bytes, mime, status, uploaded_by, uploaded_at, anchored, anchor_id}. Unique compound index {document_id, version_no}; index sha256. Provide only insert + a whitelisted update_status(); no other mutation path.
- POST /documents (require document:upload + require_geofence): multipart file + metadata + {lat,lng,accuracy,timestamp}.
    File validation: size <= MAX_UPLOAD_MB; MIME allow-list (pdf, docx, txt, png/jpg if needed); magic-byte check with python-magic that content matches claimed type; reject mismatch (422). 
    Flow (transactional-ish, no orphan metadata): validate -> put_object(encrypted) -> sha256 -> insert documents + document_versions V1 (status DRAFT, prev_version_hash=null) -> return 201 {document_id, version_id, sha256, status}. If storage fails, do NOT write metadata (503).
- GET /documents (search/list, paginated, filters: query,status,doc_type,owner,date range) require document:view.
- GET /documents/{id} metadata require document:view.
- GET /documents/{id}/download (require document:view + require_geofence): return a short-lived pre-signed URL; do not stream bytes through API.
- GET /documents/{id}/versions require document:view: full lineage.

Tests: sha256 known-vector; identical bytes -> identical hash; 1-byte change -> different hash; valid pdf upload -> 201 with stored key + hash + V1 DRAFT; oversized file -> 413/422; mime/magic mismatch -> 422; download returns a working pre-signed URL; version_no uniqueness enforced.

STOP at the PHASE 4 DoD checklist.
```

**DoD:**
- [ ] Upload validates size + MIME + magic bytes; bad files rejected pre-storage.
- [ ] File stored encrypted in R2/MinIO under a server-generated UUID key; bucket private.
- [ ] SHA-256 computed on stored bytes and saved on the version.
- [ ] `documents` + `document_versions` V1 (DRAFT) created; `prev_version_hash` supported.
- [ ] `document_versions` is insert-only (no update path except whitelisted status).
- [ ] Download returns a working short-lived pre-signed URL (no API proxying).
- [ ] Storage failure produces no orphan metadata.
- [ ] Tests pass.

**Verify:** `pytest -k "hashing or upload"` ; manual: upload a PDF, confirm object in MinIO console, confirm hash in Mongo, open pre-signed URL.

---

## PHASE 5 — Smart Contract + Deploy Sepolia + Anchor Service

**Goal:** `DocumentAnchor` contract, Hardhat tests, deploy to Sepolia, backend `blockchain.py` that signs with the service wallet and records anchors. (Parts 12, 18.)

**Depends on:** Phase 4.

**Deliverables:** `contracts/contracts/DocumentAnchor.sol`, `contracts/test/DocumentAnchor.test.ts`, `contracts/scripts/deploy.ts`, `contracts/hardhat.config.ts`, `backend/app/services/blockchain.py`, `backend/app/modules/blockchain/{router,service,models}.py`, tests `tests/integration/test_anchor.py`.

**PROMPT ►**
```
Implement PHASE 5 (Smart Contract + Anchoring) per Plan Parts 12 and 18. Do ONLY this phase. Obey GUARDRAILS #1 (only hash+metadata on-chain), #2 (key in env only), #3 (backend service wallet signs).

contracts/ (Hardhat + TypeScript):
- DocumentAnchor.sol EXACTLY per Plan Part 12: owner + writers mapping; struct Anchor{bytes32 hash; uint32 version; uint8 eventType; uint64 ts; bool exists}; mapping key = keccak256(documentId, version); anchor(string documentId, uint32 version, bytes32 hash, uint8 eventType) onlyWriter, revert if already exists; getAnchor(...) view; event AnchorCreated(...). No upgradeability, no tokens.
- hardhat.config.ts: sepolia network from SEPOLIA_RPC_URL + SERVICE_WALLET_PRIVATE_KEY (read from env; never hardcode).
- test/DocumentAnchor.test.ts: anchor stores hash; re-anchor same (doc,version) reverts; onlyWriter enforced; getAnchor returns stored values; setWriter only by owner.
- scripts/deploy.ts: deploy, print address; I will paste it into CONTRACT_ADDRESS.

backend services/blockchain.py (web3.py):
- Load provider from SEPOLIA_RPC_URL, account from SERVICE_WALLET_PRIVATE_KEY, contract from CONTRACT_ADDRESS + ABI.
- anchor_hash(document_id, version, sha256_hex, event_type_int) -> builds, signs, sends tx; returns tx_hash. Handle nonce (serialize sends), gas estimation, and errors. Convert sha256 hex -> bytes32.
- get_onchain_anchor(document_id, version) -> reads contract mapping, returns {hash, event_type, ts, exists}.
- confirm_tx(tx_hash) -> receipt + block number once >= ANCHOR_CONFIRMATIONS.

blockchain module:
- blockchain_anchors collection: {_id, document_id, version_id, sha256, event_type, tx_hash(unique), block_number, contract_address, network, status(PENDING|CONFIRMED|FAILED), created_at, confirmed_at}.
- GET /blockchain/anchor/{version_id}: return the stored anchor + on-chain read + an Etherscan URL (https://sepolia.etherscan.io/tx/{hash}).
- Do NOT expose any endpoint that anchors on user demand — anchoring is triggered only by approval (Phase 6).

Failure handling: RPC down or revert -> mark PENDING/FAILED, do not crash the request; log for retry. Provide a retry-able anchor path used later by the worker.

Tests: Hardhat contract tests all pass; a mocked/integration test that anchor_hash records a PENDING anchor and get_onchain_anchor reads it back (mock web3 or use a local hardhat node).

STOP at the PHASE 5 DoD checklist. Tell me the exact manual steps: fund the service wallet from a Sepolia faucet, run deploy, set CONTRACT_ADDRESS.
```

**DoD:**
- [ ] Hardhat tests pass (anchor stores; re-anchor reverts; onlyWriter; getAnchor; owner-only setWriter).
- [ ] Contract deployed to Sepolia; address recorded in `CONTRACT_ADDRESS`.
- [ ] Service wallet funded from faucet; backend can read/write the contract.
- [ ] `anchor_hash` records a PENDING `blockchain_anchors` row with a real tx hash; `get_onchain_anchor` reads it back.
- [ ] No user-triggered anchoring endpoint exists; key only in env.
- [ ] Etherscan link resolves to the tx.

**Verify:** `cd contracts && npx hardhat test` ; deploy script prints an address; call the anchor service from a script and open the Etherscan link.

---
## PHASE 6 — Lifecycle Workflow (State Machine + Review/Approve/Amend + Anchoring)

**Goal:** The full document state machine; approval triggers anchoring; amendment creates immutable V(n+1); maker≠checker enforced. (Parts 5, 4, 17.)

**Depends on:** Phases 4–5.

**Deliverables:** `backend/app/modules/documents/workflow.py` (state machine), transition endpoints, `backend/app/workers/anchor_confirmer.py` (optional but recommended), tests `tests/integration/test_workflow.py`.

**PROMPT ►**
```
Implement PHASE 6 (Lifecycle Workflow) per Plan Part 5 (state machine table) and Part 4/17. Do ONLY this phase. Obey GUARDRAILS #3 (auto-anchor on approve), #7 (immutable versions), #5 (pipeline). Follow the Part 5 transition table EXACTLY (who triggers / validation / db change / blockchain / audit / failure).

States: DRAFT, SUBMITTED, UNDER_REVIEW, PENDING_APPROVAL, CHANGES_REQUESTED, APPROVED, BLOCKCHAIN_ANCHORED, ACTIVE, AMENDMENT_REQUESTED, SUPERSEDED, ARCHIVED.

workflow.py: a transition function that validates the allowed source->target, the actor's permission, and (for sensitive transitions) geofence, then applies DB changes atomically and records the intended audit action (audit implemented in Phase 8; call an audit stub now).

Endpoints (all require appropriate permission; approve & amend also require_geofence):
- POST /documents/{id}/submit (owner): DRAFT -> SUBMITTED.
- POST /documents/{id}/review (REVIEWING_OFFICER, reviewer != uploader): SUBMITTED->UNDER_REVIEW, and decision approve -> PENDING_APPROVAL OR changes_requested (comment required) -> CHANGES_REQUESTED -> DRAFT.
- POST /documents/{id}/approve (LEGAL_OFFICER, enforce_maker_checker approver != uploader): PENDING_APPROVAL -> APPROVED, then ENQUEUE anchoring of that version (event_type=APPROVED). On successful send: create blockchain_anchors PENDING; status APPROVED (pending anchor). When confirmed (worker or synchronous fallback): version.anchored=true, anchor_id set, version.status BLOCKCHAIN_ANCHORED -> ACTIVE; documents.current_version_id -> this version; documents.status ACTIVE.
- POST /documents/{id}/amend (LEGAL_OFFICER or AUTHORIZED_STAFF): ACTIVE -> AMENDMENT_REQUESTED (reason required). Then a new upload creates version V(n+1) DRAFT with prev_version_hash = current version's sha256 (reuse Phase 4 upload path with an amend flag). On approval of V(n+1): it becomes ACTIVE and the previous ACTIVE version becomes SUPERSEDED (retained, still verifiable). NEVER overwrite V(n).
- POST /documents/{id}/archive (ADMINISTRATOR or LEGAL_OFFICER): ACTIVE/SUPERSEDED -> ARCHIVED.

Anchor failure handling (Part 5 last column): if the anchor tx fails/reverts/times out, the document stays APPROVED (pending anchor); retry with backoff up to k times; after k, keep pending and surface an alert flag. The app must remain usable meanwhile.

workers/anchor_confirmer.py (optional worker, or a synchronous confirm fallback if worker not run): poll PENDING anchors, confirm_tx, on CONFIRMED promote APPROVED->BLOCKCHAIN_ANCHORED->ACTIVE and set version.anchored.

Tests: full happy path DRAFT->...->ACTIVE with a (mocked or hardhat-local) anchor; approver==uploader blocked; changes_requested loops to DRAFT; amendment creates V2 with correct prev_version_hash and marks V1 SUPERSEDED without mutating V1's bytes/hash; anchor failure keeps doc APPROVED(pending) and app stays responsive; illegal transition (e.g. DRAFT->ACTIVE) rejected.

STOP at the PHASE 6 DoD checklist.
```

**DoD:**
- [ ] Every transition matches the Part 5 table (trigger, validation, DB change, chain action, audit intent).
- [ ] Approval auto-enqueues anchoring; on confirmation the version → BLOCKCHAIN_ANCHORED → ACTIVE.
- [ ] `enforce_maker_checker` blocks approver == uploader; CHANGES_REQUESTED loops to DRAFT.
- [ ] Amendment creates immutable V2 with `prev_version_hash = V1.sha256`; V1 becomes SUPERSEDED, never overwritten.
- [ ] Anchor failure leaves doc APPROVED(pending) + retry; app stays usable.
- [ ] Illegal transitions rejected.
- [ ] Tests pass.

**Verify:** `pytest -k workflow` ; manual: run a doc end-to-end to ACTIVE, then amend to V2, confirm both versions exist with distinct hashes.

---

## PHASE 7 — ★ Verification Loop (3-Way, Tamper Detection) — the product core

**Goal:** Recompute SHA-256 from stored bytes and compare against (a) stored hash and (b) on-chain hash → VERIFIED / MISMATCH / NOT_ANCHORED. Record every verification. This is the demo money-shot (Part 6 Scenario 5). (Parts 6, 13, 17.)

**Depends on:** Phases 4–6.

**Deliverables:** `backend/app/modules/verify/{router,service,models}.py`, `verification_records` collection, tests `tests/integration/test_verify.py` including a controlled-tamper case.

**PROMPT ►**
```
Implement PHASE 7 (Verification Loop) per Plan Part 6 (Scenario 5), Part 13, Part 17. Do ONLY this phase. This is the core feature — make it robust.

POST /verify/{version_id} (require verify:perform):
  1. Load version -> storage_key, stored sha256, document_id, version_no.
  2. Fetch current bytes from R2/MinIO (server-side).
  3. Recompute SHA-256.
  4. Read on-chain hash via get_onchain_anchor(document_id, version_no).
  5. Compare (constant-time) recomputed vs stored vs on-chain:
     - all three equal -> VERIFIED
     - recomputed != stored OR recomputed != onchain -> MISMATCH (tamper detected)
     - not anchored yet -> NOT_ANCHORED (recomputed vs stored still reported; not an error)
  6. Insert verification_records {version_id, requested_by, recomputed_hash, stored_hash, onchain_hash, result, created_at}.
  7. On MISMATCH: flag the document (e.g. documents.integrity_flag=TAMPERED) and emit an alert log; (Phase 8 will audit VERIFY_FAIL).
  8. Return {result, recomputed, stored, onchain, tx_hash, etherscan_url}.

GET /verify/{version_id}/history (require verify:perform or audit:view): past verification_records for the version.

Tests:
- Untouched anchored version -> VERIFIED (all three hashes equal).
- Controlled tamper: after anchoring, overwrite the stored blob with 1 changed byte, then verify -> MISMATCH; document flagged TAMPERED.
- Tamper the STORED hash in Mongo to match a tampered file -> still MISMATCH vs on-chain (proves the point of anchoring).
- Never-anchored version -> NOT_ANCHORED.

STOP at the PHASE 7 DoD checklist.
```

**DoD:**
- [ ] Verify recomputes from actual stored bytes and compares against stored + on-chain.
- [ ] Untouched version → VERIFIED; 1-byte tamper → MISMATCH; DB-hash tamper still → MISMATCH vs chain.
- [ ] NOT_ANCHORED handled cleanly (not an error).
- [ ] `verification_records` written every time; MISMATCH flags the document + alerts.
- [ ] Response includes both hashes and the Etherscan link.
- [ ] Tests (incl. controlled tamper) pass.

**Verify:** `pytest -k verify` ; manual: verify a good doc (green), overwrite its blob in MinIO, verify again (red MISMATCH).

---

## PHASE 8 — Audit Logging + Observability

**Goal:** Append-only audit trail of every security-relevant action; structured logs; health/metrics. (Parts 20, 32.)

**Depends on:** Phases 1–7 (wire audit into all prior actions).

**Deliverables:** `backend/app/modules/audit/{router,service,models}.py`, an audit helper used across modules, Sentry init, tests `tests/api/test_audit.py`.

**PROMPT ►**
```
Implement PHASE 8 (Audit + Observability) per Plan Parts 20 and 32. Do ONLY this phase.

audit_logs collection (append-only): {_id, actor_id, action, target_type, target_id, result, ip, location(GeoJSON Point)?, meta, created_at}. Index {actor_id, created_at desc}, action, 2dsphere on location. Consider a time-series or capped collection; writes only via an append-only helper (no update/delete API).

audit.record(actor_id, action, target_type, target_id, result, ip, location, meta): call it from EVERY security-relevant action implemented in Phases 1-7 — LOGIN_SUCCESS/FAILURE, USER_CREATE, GEOFENCE_DENIED, GEOFENCE_CREATE, UPLOAD, ACCESS/ACCESS_DENIED, SUBMIT, REVIEW_*, APPROVE, ANCHOR_OK/ANCHOR_FAIL, AMEND_REQ, ARCHIVE, VERIFY_PASS/VERIFY_FAIL. Replace the audit stubs from earlier phases with real calls.

GET /audit (require audit:view — AUDITOR/ADMINISTRATOR only): filter by actor, action, result, date range, target; paginated. Non-auditor -> 403.

Observability: initialize Sentry from SENTRY_DSN if set; ensure the JSON logging middleware (Phase 0) logs security events (GEOFENCE_DENIED, auth failures, ANCHOR_FAIL, VERIFY_FAIL) at WARN/ERROR. Extend /api/v1/health to report mongo + storage + chain reachability.

Tests: an action produces exactly one audit record with correct fields; audit_logs cannot be updated/deleted via API; non-auditor gets 403 on /audit; VERIFY_FAIL from Phase 7 appears in the log.

STOP at the PHASE 8 DoD checklist.
```

**DoD:**
- [ ] Every security-relevant action writes one append-only audit record.
- [ ] `audit_logs` has no update/delete API path; indexes incl. 2dsphere on location.
- [ ] `/audit` is Auditor/Admin-only; filters + pagination work.
- [ ] Sentry (if DSN set) + structured WARN/ERROR logs for security events.
- [ ] Health check reports all dependencies.
- [ ] Tests pass.

**Verify:** `pytest -k audit` ; manual: perform login, upload, geofence-deny, verify-fail → all appear in `/audit`.

---

## PHASE 9 — Frontend (All Core Pages)

**Goal:** Usable SPA implementing the pages in Part 16 with the location gate and the verify page front-and-center. (Part 16.)

**Depends on:** Phases 1–8 (backend endpoints exist).

**Deliverables:** `frontend/src/pages/*`, `frontend/src/components/*`, `frontend/src/api/*` (typed clients), `frontend/src/context/AuthContext.tsx`, `frontend/src/components/LocationGate.tsx`.

**PROMPT ►**
```
Implement PHASE 9 (Frontend) per Plan Part 16. Do ONLY this phase. React + Vite + TS + Tailwind + React Router + TanStack Query. Access token in memory; refresh via httpOnly cookie. Obey GUARDRAIL #6 (no "military-grade"/"tamper-proof" text anywhere in UI).

Global:
- AuthContext: login/logout, current user + role, token refresh interceptor (on 401 -> refresh -> retry once).
- API layer: typed fetch wrappers per module, base URL from VITE_API_BASE_URL, attaches Authorization header.
- LocationGate component/hook: calls navigator.geolocation.getCurrentPosition, obtains {lat,lng,accuracy,timestamp}, and attaches them to sensitive requests (upload/download/approve/amend). If permission denied or accuracy poor, show a clear blocking message. Never compute allow/deny on the client — always send coordinates and let the server decide.
- Sidebar shows only items permitted for the user's role (mirror Part 3).

Pages (Part 16 table): Login; Dashboard (role badge + geofence status + my drafts + counts); Document Repository (search/filter/paginate); Upload (dropzone + metadata + location gate + client-side size/type hints, server is source of truth); Document Details (metadata, status, download, VERIFY button, amend); Version History (timeline of V1..Vn with SUPERSEDED flags + per-version verify + Etherscan link); Amendment Request (reason + upload); Verification (BIG green VERIFIED / red MISMATCH, 3-way hash compare, tx link); Geofence Status (current point vs fence, in/out badge, accuracy); Audit Logs (Auditor/Admin only, filters); Blockchain Verification (tx hash, block, Etherscan link); Admin Panel; User Management (Admin); Settings (change password).

Every page: loading, empty, and error states. Show WHY an action was denied (auth vs role vs location) using the server error code.

STOP at the PHASE 9 DoD checklist.
```

**DoD:**
- [ ] Login → role-appropriate dashboard; sidebar hides unpermitted items.
- [ ] Upload works with the location gate; outside-geofence upload is blocked with a clear reason.
- [ ] Repository search/filter/paginate works; details page shows metadata + status.
- [ ] Version History shows lineage with SUPERSEDED flags + per-version verify + Etherscan links.
- [ ] Verify page renders green VERIFIED / red MISMATCH with the 3-way hash compare and tx link.
- [ ] Audit page is Auditor/Admin-only; all pages have loading/empty/error states.
- [ ] No prohibited security-claim wording anywhere in the UI.

**Verify:** manual click-through of the full happy path + the tamper-detect path in the browser.

---

## PHASE 10 — Admin, User Management, Reporting, Archival (Level-2)

**Goal:** Admin panel, user management UI, simple reports, archival flow polish. (Parts 2, 3, 16 — SHOULD-HAVE.)

**Depends on:** Phases 8–9.

**Deliverables:** `backend/app/modules/reports/{router,service}.py`, admin UI pages, archival endpoints wired to UI.

**PROMPT ►**
```
Implement PHASE 10 (Admin + Reporting + Archival) per Plan Parts 2, 3, 16 (Level-2). Do ONLY this phase.

Backend reports module (require audit:view or a reports:view perm): aggregation endpoints:
- GET /reports/summary: counts by status/doc_type, anchoring success rate (CONFIRMED vs FAILED), recent verifications (pass/fail), access-denied (GEOFENCE_DENIED) counts. Simple Mongo aggregation, paginated where needed.

Frontend:
- Admin Panel with tabs: Users, Geofences, Reports, System Health (calls /health).
- User Management UI: list/create/deactivate users, assign role + geofences (Admin only).
- Reporting dashboard: render /reports/summary as cards + a couple of simple charts.
- Archival: wire POST /documents/{id}/archive into Document Details; ARCHIVED docs hidden from default repository view but reachable via a filter; all versions + anchors retained.

Tests: report aggregation returns correct counts on seeded data; archive hides from default list but retains versions/anchors; only Admin can manage users/geofences.

STOP at the PHASE 10 DoD checklist.
```

**DoD:**
- [ ] Admin can manage users + geofences from the UI; role/geofence assignment works.
- [ ] `/reports/summary` returns correct aggregates; dashboard renders them.
- [ ] Archival hides docs from default view but retains all versions + anchors.
- [ ] Tests pass.

**Verify:** `pytest -k reports` ; manual: archive a doc, confirm it's hidden yet still verifiable.

---
## PHASE 11 — Testing Suite + CI

**Goal:** Complete the test pyramid and a green GitHub Actions pipeline. (Parts 20, 19.)

**Depends on:** all prior phases.

**Deliverables:** filled-out `backend/tests/{unit,integration,api}/`, `contracts/test/`, `frontend` component tests (Vitest/RTL), `.github/workflows/ci.yml`, coverage config.

**PROMPT ►**
```
Implement PHASE 11 (Testing + CI) per Plan Part 20 (test plan) and Part 19 (CI). Do ONLY this phase. Fill gaps; don't rewrite passing tests.

Backend:
- Unit: hashing (known vectors, 1-byte change), geofence point-in-polygon (inside/outside/edge), RBAC map (each role's allow/deny), state-machine transitions (legal + illegal), maker-checker.
- Integration: upload->store->hash->metadata; approve->anchor (hardhat-local or mocked web3); verify VERIFIED + MISMATCH + NOT_ANCHORED; amendment V1->V2 immutability.
- API: every endpoint x each role (authz matrix) — parametrized; expired JWT->401; alg=none->reject; IDOR (other user's doc id)->403; NoSQL-injection payload in query -> safely handled; malicious filename -> stored as UUID; oversized/wrong-MIME upload -> 422.
- Use a disposable test Mongo (testcontainers or a dedicated test DB) and MinIO/mock storage.

Contracts: ensure Hardhat tests cover anchor, re-anchor revert, onlyWriter, getAnchor, owner-only setWriter.

Frontend: Vitest + React Testing Library for login form validation, upload validation, verify-result rendering (green/red).

CI (.github/workflows/ci.yml): on pull_request + push to main:
- job backend: setup python, install, ruff lint, pytest with coverage (fail under ~60% on core modules).
- job contracts: npm ci, npx hardhat test.
- job frontend: npm ci, eslint, vitest, build.
- Cache deps. All jobs must pass to merge (document branch protection).

STOP at the PHASE 11 DoD checklist. Report coverage numbers.
```

**DoD:**
- [ ] Unit/integration/API/contract/frontend tests present and passing locally.
- [ ] Authz matrix test covers every role × representative endpoints.
- [ ] Security cases (expired JWT, alg=none, IDOR, injection, malicious filename, bad upload) covered.
- [ ] CI runs all jobs green on a PR; coverage ≥ target on core modules.

**Verify:** open a PR → all CI jobs green; `pytest --cov` locally.

---

## PHASE 12 — Deployment + Documentation + Demo

**Goal:** Ship the demo stack (Vercel + Render + Atlas + R2 + Sepolia), complete the doc set, and rehearse the 10-minute demo. (Parts 30–34, 33.)

**Depends on:** all prior phases + green CI.

**Deliverables:** `docs/{DEPLOYMENT.md, DEMO_SCRIPT.md, THREAT_MODEL.md, API.md, DB_DESIGN.md, USER_GUIDE.md, DEVELOPER_GUIDE.md, SRS.md, TEST_PLAN.md, RESEARCH.md}`, `scripts/seed.py`, production config.

**PROMPT ►**
```
Implement PHASE 12 (Deployment + Docs + Demo) per Plan Parts 30-34 and 33. Do ONLY this phase. Obey GUARDRAIL #6 (no overstated security claims in any doc — use tamper-evident, prototype-grade geofencing).

Deployment (follow Plan Part 30 sequence exactly):
- Provide DEPLOYMENT.md with the exact order: (1) deploy DocumentAnchor.sol to Sepolia + fund service wallet + record CONTRACT_ADDRESS; (2) Atlas M0 (user + IP allow-list) + create indexes; (3) R2 bucket (private + scoped key); (4) set backend env in Render + deploy + run seed + verify /health; (5) set frontend env + deploy to Vercel; (6) smoke test happy path + tamper path; (7) enable Sentry + snapshot DB.
- Backend: production-ready Dockerfile, gunicorn/uvicorn workers, CORS locked to the Vercel origin, security headers, rate limiting enabled.
- scripts/seed.py: one user per role, an HQ geofence polygon + an outside/denied location, ~30-50 synthetic documents (public-template/placeholder text, fake parties — NEVER real confidential docs, per Plan Part 21), several with V2 amendments, and 5 controlled-tamper cases pre-set for the demo.

Documentation set (Plan Part 33 structure): SRS, Architecture (reference the plan's horizontal ASCII diagrams), API.md (link the auto OpenAPI + error catalogue), DB_DESIGN.md, THREAT_MODEL.md (Part 14 table + honest limitations, esp. browser-GPS spoofability), TEST_PLAN.md, DEPLOYMENT.md, USER_GUIDE.md (per role), DEVELOPER_GUIDE.md (local setup), RESEARCH.md (RQ, method, metrics, baselines, limitations per Part 29).

DEMO_SCRIPT.md: the exact 10-minute sequence from Plan Part 34 (login -> role -> geofence -> upload -> R2 object -> Mongo metadata -> hash -> approve+anchor -> Etherscan -> amend V2 -> unauthorized blob overwrite -> verify V2 MISMATCH red -> verify V1 VERIFIED green -> audit trail -> outside-geofence 403 -> closing honest-limitations slide), noting exactly what must be on screen at each step.

STOP at the PHASE 12 DoD checklist. List every manual cloud step I must perform (Atlas, R2, Render, Vercel, faucet).
```

**DoD:**
- [ ] Contract on Sepolia; backend on Render; frontend on Vercel; Atlas M0 + R2 wired; `/health` green in the cloud.
- [ ] Seed script populates roles, geofences, ~30–50 synthetic docs, V2 amendments, 5 tamper cases — no real confidential documents.
- [ ] CORS locked to the frontend origin; security headers + rate limiting on; no secrets in git.
- [ ] Full doc set present and free of overstated security claims (tamper-evident, prototype geofencing).
- [ ] `DEMO_SCRIPT.md` runs end-to-end twice with no manual DB fixes.

**Verify:** run the demo script live twice; `curl` the cloud `/health`; `git secrets`/`gitleaks` scan clean.

---

## PHASE 13 — Optional Level-3 (only if ahead of schedule)

**Goal:** Nice-to-haves that do NOT threaten completion. (Part 26 Level-3.)

**Depends on:** MVP shipped (Phases 0–12) and time remaining.

**PROMPT ►**
```
Implement PHASE 13 (Level-3, only the items I name) per Plan Part 26. Do ONLY the item(s) I list; each behind a feature flag; never break the MVP.
Candidates (pick per remaining time): ClamAV malware scan on upload; email notifications for review/approval; Playwright e2e for the two golden paths; GPS-spoof heuristics (implausible velocity, GPS-vs-IP mismatch — LOG/FLAG only, never claim prevention); audit-log batch hashing; export/PDF reports; re-anchoring capability if Sepolia resets.
STOP at a DoD checklist for the specific item(s).
```

**DoD (per item):**
- [ ] Feature is behind a flag and off by default; MVP paths unaffected.
- [ ] Item works and is tested; no overstated claims (spoof heuristics = detect/flag, not prevent).
- [ ] CI still green.

---

## GLOBAL DEFINITION OF DONE (project complete — mirrors Plan Part G)

Do not consider the project finished until ALL are true:

- [ ] Admin can provision users; users log in and receive a valid JWT.
- [ ] Sensitive operations are blocked outside an authorized geofence (server-side) and allowed inside — shown with two locations.
- [ ] A document uploads, is encrypted at rest in R2, is SHA-256 hashed, and its metadata + version are stored in MongoDB.
- [ ] Approval anchors the version's hash on Sepolia; the tx is on Etherscan and stored in `blockchain_anchors`.
- [ ] Amendment creates V2 without destroying V1; both versions independently verify.
- [ ] Verify recomputes and compares to stored + on-chain: **VERIFIED** for an untouched file, **MISMATCH** for a tampered one (live).
- [ ] Every security-relevant action is in an append-only audit log visible to Auditor/Admin.
- [ ] RBAC enforced on every endpoint (tested per role); deny-by-default holds.
- [ ] Full 10-minute demo runs end-to-end twice with no manual DB fixes.
- [ ] Core services tested; CI green on main.
- [ ] Full documentation set complete (SRS, architecture, threat model with honest limits, API, DB, test plan, deploy, user/dev guides, report, PPT, demo script).
- [ ] No secrets in git; all keys in env/secret store; **no "military-grade"/"tamper-proof" claims anywhere.**

---

## QUICK-REFERENCE: what to paste, in order

1. MASTER GUARDRAILS block (every session).
2. Phase 0 `PROMPT ►` → verify → commit.
3. Phases 1 → 7 in order (this is the MVP loop; do not skip or reorder). Verify + commit after each.
4. Phases 8 → 12 (harden, UI, ship). Verify + commit after each.
5. Phase 13 only if time remains.

**Golden rule (Plan Part 37 #5):** if you fall behind, cut in this order — email notifications → ClamAV → reporting → spoof heuristics → admin UI polish → Auditor role → background worker (anchor synchronously with a spinner). **Never cut** the upload→hash→anchor→verify→tamper-detect loop or the geofence check.

*End of phase-wise implementation prompt. Build the tamper-detection loop first; keep the honesty about geofencing throughout.*
