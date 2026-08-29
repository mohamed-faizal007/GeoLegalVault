# CLAUDE.md — GeoLegalVault Project Rules (read this every session)

You are helping build **GeoLegalVault**, a geospatially-aware document integrity & lifecycle platform.
Two authoritative documents live in `docs/`:

- `docs/GeoLegalVault_Project_Plan.md` — the design/architecture. **If anything conflicts, the plan wins. Stop and ask.**
- `docs/IMPLEMENTATION_PROMPT.md` — the phase-by-phase build script. Work **one phase at a time**, in order.

**Always read both `docs/` files before writing code.** Do only the phase the user names. Stop at that phase's DoD checklist and report each item done/not-done plus any manual steps the user must perform. Do not start the next phase, and do not invent scope beyond the current phase.

---

## MASTER GUARDRAILS (never break, in any phase)

1. **Documents stay off-chain.** Only anchor `{documentId, version, sha256 hash, eventType, timestamp}` on Ethereum Sepolia. Never put file bytes, names, or PII on-chain.
2. **No secrets in git.** Private keys, RPC URLs with keys, DB URIs, R2 keys, JWT secrets live only in `.env` (gitignored) / platform env. Commit only `.env.example` with placeholder values. Add secret patterns to `.gitignore`.
3. **Backend service-wallet signs anchors.** Do NOT use per-user MetaMask. The backend holds ONE service wallet key (env var) and signs anchoring txns. Anchoring is an automatic system event on APPROVAL, never a user action. No user-triggered anchoring endpoint.
4. **Storage is Cloudflare R2** (S3-compatible; MinIO locally), **private bucket**, access only via short-lived pre-signed URLs. Never make buckets public. Never proxy large files through the API.
5. **Enforcement pipeline, in this exact order,** on every sensitive op: TLS → JWT verify → RBAC (deny-by-default) → server-side geofence check → input/file validation → action → audit log. The geofence check is ALWAYS server-side; NEVER trust a client `allowed=true` flag.
6. **Geofence is policy, not a security guarantee.** Browser GPS is spoofable. No code comments, docs, UI text, or logs may claim "military-grade", "tamper-proof", "unhackable", or "guaranteed location". Use "tamper-evident", "detects modification", "policy-level geofencing", "prototype".
7. **Versions are immutable.** `document_versions` is insert-only. Amendment creates V(n+1) with `prev_version_hash` pointing to V(n)'s hash. NEVER overwrite or mutate an existing version's content/hash. Only a whitelisted `status` field may change.
8. **Do NOT build (out of scope):** Merkle/hierarchical hashing, NLP, microservices/message brokers, mainnet, on-chain storage, multi-tenant billing, contract upgradeability proxies, real GPS hardware attestation. (These belong to TARP or are unnecessary.)
9. **GeoJSON is `[longitude, latitude]` order.** Validate coordinate order and ranges on every input. This is the #1 geofence bug.
10. **Modular monolith.** One FastAPI app, organized by module. No separate services/queues except ONE optional background worker for blockchain confirmation polling.
11. **Tests are not optional** for core services (hashing, geofence, RBAC, state machine, contract). Write them in the same phase as the code.
12. When unsure about a design decision, re-read the relevant Part of the plan and follow it. Do not invent scope.

---

## LOCKED STACK (do not substitute without being asked)

- **Frontend:** React + Vite + TypeScript + Tailwind + React Router + TanStack Query. Access token in memory; refresh via httpOnly cookie.
- **Backend:** Python 3.11+ + FastAPI + Pydantic (modular monolith). Motor (async MongoDB).
- **Auth:** JWT (HS256, pin the alg, reject `none`) + Argon2id password hashing.
- **DB:** MongoDB with `2dsphere` indexes (Atlas in cloud, `mongo:7` locally).
- **Storage:** Cloudflare R2 (S3-compatible via boto3); MinIO locally.
- **Blockchain:** Solidity + Hardhat + web3.py + Ethereum Sepolia (Alchemy RPC).
- **DevOps:** Docker + docker-compose + GitHub Actions. **Observability:** Sentry + structured JSON logs.
- **Cost target: ₹0** — testnet only, R2 (no egress fees), free tiers, small file caps.

## ROLES (deny-by-default; maker ≠ checker)

ADMINISTRATOR · LEGAL_OFFICER · REVIEWING_OFFICER · AUTHORIZED_STAFF · AUDITOR.
Admin manages the system but cannot approve documents. Auditor is read-only everywhere but can view audit logs. The approver of a version must never be its uploader.

## LIFECYCLE STATES

DRAFT → SUBMITTED → UNDER_REVIEW → PENDING_APPROVAL → APPROVED → BLOCKCHAIN_ANCHORED → ACTIVE → (AMENDMENT_REQUESTED → new DRAFT V(n+1)); ACTIVE/SUPERSEDED → ARCHIVED. CHANGES_REQUESTED loops back to DRAFT. Approval auto-enqueues anchoring. An amendment supersedes but never destroys the prior version.

## CORE FEATURE (the product)

The **3-way verification loop**: recompute SHA-256 from the stored bytes and compare against (a) the stored hash and (b) the on-chain hash → **VERIFIED / MISMATCH / NOT_ANCHORED**. This is what makes the system more than CRUD. Build toward it; never cut it.

---

## WORKING AGREEMENT

- One phase per session. Start each phase from a clean context. Stop at the DoD checklist.
- After each phase: the user runs Verify commands, checks the DoD boxes, and commits. Do not assume the next phase has started.
- Never leave orphaned data on failure (e.g. no metadata row if storage write fails).
- Never print or log secrets. Never hardcode a private key, even in tests — read from env.
- If you cannot complete a DoD item, say so explicitly rather than marking it done.

**Golden rule (if behind schedule):** cut in this order — email notifications → ClamAV → reporting → spoof heuristics → admin UI polish → Auditor role → background worker (anchor synchronously with a spinner). **Never cut** the upload→hash→anchor→verify→tamper-detect loop or the geofence check.