# CLAUDE.md

This file is the canonical guardrails document for GeoLegalVault. It is referenced from
`README.md`'s "Guardrails" section and from the top of `docs/IMPLEMENTATION_PROMPT.md`
("MASTER GUARDRAILS"), and individual guardrails are cited by number throughout the codebase
(e.g. `Guardrail #1`, `Guardrail #7`) in docstrings and comments across `backend/app/services/`,
`backend/app/modules/`, `contracts/`, `frontend/src/`, and `docs/`.

**Why this file exists:** these are constraints that must never be violated when extending
this project, whether by a human contributor or an AI coding assistant. They encode security,
scope, and honesty decisions made early in the project (see `docs/GeoLegalVault_Project_Plan.md`
and `docs/THREAT_MODEL.md`) that are cheap to violate accidentally (e.g. adding a convenience
endpoint that bypasses geofence checks, or overstating what geofencing guarantees) and expensive
to unwind once shipped. If anything elsewhere in the docs conflicts with this file, treat that
as a bug to flag, not license to ignore the guardrail.

Every guardrail below was cross-checked against the actual implementation (not just the comment
claiming it) as of this writing. All 12 hold.

---

## 1. Documents stay off-chain

Only `{documentId, version, sha256 hash, eventType, timestamp}` is ever anchored on Ethereum
Sepolia. File bytes, filenames, and PII never go on-chain.

**Why:** the chain is a public, immutable record. Putting document content or identifying
metadata there would make a confidentiality breach permanent and unfixable.

**Enforced at:**
- [`contracts/contracts/DocumentAnchor.sol:4-8`](contracts/contracts/DocumentAnchor.sol#L4-L8) — the `Anchor` struct only stores `hash`, `version`, `eventType`, `ts`.
- [`backend/app/services/blockchain.py:1-12`](backend/app/services/blockchain.py#L1-L12) — the only code path that calls the contract's `anchor()` function.

**Don't:** add any on-chain field carrying file content, a filename, a user's name/email, or
any other PII. Don't add an on-chain "notes" or "description" field.

---

## 2. No secrets in git

Private keys, RPC URLs with embedded keys, DB URIs, R2 keys, and JWT secrets live only in
`.env` (gitignored) or platform env vars. Only `.env.example` (placeholder values) is committed.

**Why:** a leaked service-wallet key or DB URI is a full compromise; git history is effectively
permanent even after a "fix" commit.

**Enforced at:**
- [`.gitignore`](.gitignore) — excludes `.env`, `.env.*`, keeps `!.env.example`; also excludes `*.key`.
- [`contracts/hardhat.config.ts:8`](contracts/hardhat.config.ts#L8) — private key read from `contracts/.env`, never hardcoded.
- `APP_ENV != development` fails startup if any required secret is still a placeholder (per `docs/THREAT_MODEL.md` row 20).

**Don't:** commit a real `.env`, paste a real key/URI into a docstring or test fixture, or log
secret values (the blockchain service docstring at `backend/app/services/blockchain.py:5-6`
specifically calls out never logging the service-wallet key).

---

## 3. Backend service-wallet signs anchors — no user-facing wallet-connect

The backend holds exactly one service wallet key (env var) and signs all anchoring
transactions. There is no per-user MetaMask flow, and no endpoint lets a user trigger an
anchor directly — anchoring is an automatic system side effect of a document reaching
`APPROVED`.

**Why:** per-user wallets would mean asking legal/records staff to manage crypto wallets and
gas, which is out of scope for this product's users, and would multiply the ways anchoring
could go wrong or be bypassed.

**Enforced at:**
- [`backend/app/modules/documents/workflow.py:10-14`](backend/app/modules/documents/workflow.py#L10-L14) — `approve()` is the only transition that touches the chain, done automatically.
- [`backend/app/modules/blockchain/service.py:6`](backend/app/modules/blockchain/service.py#L6) — docstring confirms no user-triggered-anchor path exists.
- [`backend/app/modules/blockchain/router.py:4`](backend/app/modules/blockchain/router.py#L4) — anchoring is wired as a side effect of approval, not its own user-facing route.
- [`contracts/contracts/DocumentAnchor.sol:32-35`](contracts/contracts/DocumentAnchor.sol#L32-L35) — `onlyWriter` modifier restricts `anchor()` to addresses the owner (service wallet deployer) explicitly allow-lists.
- No wallet-connect UI exists anywhere in `frontend/src/`.

**Don't:** add a "connect wallet" button, an endpoint that lets any authenticated user call
`anchor()` directly, or a second signer/writer without going through `setWriter` deliberately
and documenting why.

---

## 4. Storage is private R2/S3-compatible, access only via short-lived pre-signed URLs

Cloudflare R2 in production, MinIO for local dev. Buckets are never public. The API never
proxies large file bytes through itself.

**Why:** a public bucket or a proxying API both turn one misconfiguration into a mass-leak
vector for confidential legal documents.

**Enforced at:**
- [`backend/app/services/storage.py:1-16`](backend/app/services/storage.py#L1-L16) — docstring and implementation: bucket is private, only egress path is a pre-signed GET URL.
- `STORAGE_PRESIGN_TTL_SEC` (default 60s per `docs/THREAT_MODEL.md` row 9) bounds URL lifetime.

**Don't:** flip a bucket to public-read for convenience, add a `/documents/{id}/raw` endpoint
that streams bytes through FastAPI, or extend the pre-signed TTL without a specific reason.

---

## 5. Enforcement pipeline order: TLS → JWT → RBAC → geofence → input/file validation → action → audit

This exact order runs on every sensitive endpoint. The geofence check is always server-side;
no endpoint ever trusts a client-supplied "allowed" flag.

**Why:** ordering matters — e.g. checking geofence before RBAC would leak location-based
information to unauthorized callers; skipping server-side geofence and trusting a client flag
makes the whole control theater.

**Enforced at:**
- [`backend/app/services/geofence.py:1-7`](backend/app/services/geofence.py#L1-L7) — "the ONLY place inside/outside is decided," always server-side.
- [`backend/app/modules/documents/service.py:3`](backend/app/modules/documents/service.py#L3) — upload flow docstring: validate → put_object → ... in guardrail-numbered order.
- [`docs/THREAT_MODEL.md:55`](docs/THREAT_MODEL.md#L55) — confirms the pipeline runs in this order on every sensitive endpoint; threat row 15 confirms no endpoint reads a client "allowed" field.
- [`frontend/src/api/http.ts:137`](frontend/src/api/http.ts#L137), [`frontend/src/components/LocationGate.tsx:11`](frontend/src/components/LocationGate.tsx#L11) — frontend explicitly treats geofence allow/deny as server-decided; client-side checks are hints only.

**Don't:** add a new sensitive endpoint that skips RBAC or geofence checks "temporarily," or
add any code path that reads/trusts a client-sent geofence result.

---

## 6. Geofencing is policy, not a security guarantee — no overstated claims

No code comment, doc, UI text, or log line may claim "military-grade," "tamper-proof,"
"unhackable," or "guaranteed location." Use "tamper-evident," "detects modification,"
"policy-level geofencing," "prototype."

**Why:** browser GPS is spoofable (DevTools location override, fake-GPS apps, spoofed
payloads). Claiming otherwise would be dishonest and could mislead someone relying on this
system's guarantees.

**Enforced at:**
- [`docs/THREAT_MODEL.md:1-7`](docs/THREAT_MODEL.md#L1-L7) — states this explicitly and names blockchain anchoring (not geofencing) as the actual tamper-evidence guarantee; "Honest limitations" section (lines 59-70) spells out GPS spoofability openly.
- [`backend/app/services/geofence.py:3-6`](backend/app/services/geofence.py#L3-L6), [`frontend/src/hooks/useGeoLocation.ts:15`](frontend/src/hooks/useGeoLocation.ts#L15), [`frontend/src/components/LocationGate.tsx:11`](frontend/src/components/LocationGate.tsx#L11) — all describe geofencing as policy/defense-in-depth, not a guarantee.
- Verified: no occurrence of "military-grade," "tamper-proof," "unhackable," or "guaranteed location" found anywhere in the codebase or docs during this review.

**Don't:** add marketing-style copy to the frontend, README, or a demo script that overstates
geofencing as unspoofable or cryptographically guaranteed.

---

## 7. Versions are immutable

`document_versions` is insert-only. An amendment creates `V(n+1)` with `prev_version_hash`
pointing at `V(n)`'s hash. An existing version's content/hash is never overwritten or mutated;
only a whitelisted `status` field may change.

**Why:** the whole tamper-evidence story depends on a version's hash being fixed forever once
created — if content could be edited in place, the on-chain anchor would no longer prove
anything about current DB state.

**Enforced at:**
- [`backend/app/modules/versions/models.py:1-5`](backend/app/modules/versions/models.py#L1-L5) — "Only `insert_version` and the whitelisted `update_status` ... may write to this collection; there is no other mutation path."
- [`backend/app/modules/versions/service.py:103`](backend/app/modules/versions/service.py#L103) — amendment flow: content/hash/storage_key untouched, only status changes.
- [`backend/app/modules/documents/service.py:285`](backend/app/modules/documents/service.py#L285) — old version is only ever marked `SUPERSEDED`, never mutated.
- [`docs/DB_DESIGN.md:100`](docs/DB_DESIGN.md#L100) — "there is no code path that can alter them."

**Don't:** add an "edit version" endpoint, a migration script that patches `content`/`hash`/
`storage_key` on an existing version document, or any write path into `document_versions`
outside `insert_version` / `update_status`.

---

## 8. No Merkle trees, NLP, or other out-of-scope analysis

Explicitly out of scope: Merkle/hierarchical hashing, NLP, microservices/message brokers,
mainnet deployment, on-chain storage, multi-tenant billing, contract upgradeability proxies,
real GPS hardware attestation.

**Why:** this is a scoped prototype (per `docs/RESEARCH.md`, `docs/SRS.md`); these
belong to a larger successor project (referred to as TARP in the plan docs) and adding them
here would blow the architecture and timeline without benefit to the current requirements.

**Enforced at:**
- [`docs/RESEARCH.md:96`](docs/RESEARCH.md#L96), [`docs/SRS.md:106`](docs/SRS.md#L106) — both explicitly note Merkle trees/NLP were considered and excluded to keep the scope boundary clean.
- Contract is a single non-upgradeable `DocumentAnchor.sol` with no proxy pattern (confirmed by reading the contract — no delegatecall, no proxy imports).

**Don't:** introduce a Merkle-tree batching scheme for anchors, add an NLP-based document
classifier/summarizer, split the backend into multiple deployed services, or add a proxy
pattern to the contract.

---

## 9. GeoJSON is always [longitude, latitude] order

Every coordinate input is validated for order — this is called out as "the #1 geofence bug."

**Why:** GeoJSON's `[lng, lat]` order is the opposite of the more common "lat, lng" convention
people default to, so it's an easy, silent way to put a geofence in the wrong place on Earth.

**Enforced at:**
- [`backend/app/modules/geofences/schemas.py:1-24`](backend/app/modules/geofences/schemas.py#L1-L24) — `_validate_position` checks `lng` against `[-180, 180]` and `lat` against `[-90, 90]` specifically to catch an accidental swap.

**Don't:** accept or construct a coordinate pair as `[lat, lng]` anywhere in geofence-related
code, even "just for one internal helper" — the whole point is there's no exception.

---

## 10. Modular monolith — no extra services/queues beyond one optional worker

One FastAPI app, organized by module. The only allowed exception is one optional background
worker for blockchain confirmation polling.

**Why:** this keeps deployment and local dev simple (Vercel + Render + one worker, per the
architecture in `docs/IMPLEMENTATION_PROMPT.md`) and matches the project's actual scale — see
Guardrail #8 (no microservices/message brokers).

**Enforced at:**
- [`backend/app/workers/anchor_confirmer.py:2`](backend/app/workers/anchor_confirmer.py#L2) — the one sanctioned background worker, explicitly framed as the guardrail's allowed exception.
- [`backend/pyproject.toml:25`](backend/pyproject.toml#L25) — comment frames the worker as part of "Guardrail's own golden-rule cut list."
- [`docs/DEVELOPER_GUIDE.md:115`](docs/DEVELOPER_GUIDE.md#L115) — reiterates no other microservices exist.

**Don't:** split auth, documents, or geofencing into separately-deployed services, or add a
message broker (Celery/RabbitMQ/etc.) for anything other than the one confirmation worker
already in place.

---

## 11. Tests are not optional for core services

Hashing, geofence, RBAC, the lifecycle state machine, and the contract must have tests written
in the same change as the code, not deferred.

**Why:** these are exactly the guardrail-enforcing components — untested changes to them are
how a guardrail silently breaks.

**Enforced at:**
- [`docs/DEVELOPER_GUIDE.md:126`](docs/DEVELOPER_GUIDE.md#L126) — states the rule directly.
- `backend/tests/` contains 20 test files across `unit/`, `api/`, and `integration/`, including `test_geofence.py`, `test_require_geofence.py`, `test_hashing.py`, `test_rbac.py`, `test_authz_matrix.py` (role × endpoint matrix), `test_workflow.py`, and `test_anchor.py` — directly covering every core service this guardrail names. Git history (commit `34bec7e`) records "full test suite (114 tests, 92% cov)."

**Don't:** merge a change to `geofence.py`, `rbac.py`, the workflow state machine, or the
contract without adding/updating tests in the same change.

---

## 12. When unsure, re-read the plan — don't invent scope

If a design decision isn't covered by the guardrails above, consult
`docs/GeoLegalVault_Project_Plan.md` (the authoritative plan) rather than guessing.

**Why:** the plan is the single source of truth this whole implementation was built against
phase-by-phase (see `docs/IMPLEMENTATION_PROMPT.md`'s phase prompts); inventing scope
piecemeal is how a tightly-scoped prototype drifts into an unmaintainable mess.

**Enforced at:** process guardrail, not code-enforced — see `docs/IMPLEMENTATION_PROMPT.md:34`.

**Don't:** add a feature, endpoint, or field because it "seems useful" without checking
whether the plan already made a decision about it (including a decision to exclude it, per
Guardrail #8).

---

## Before making changes

Before touching **auth, geofencing, blockchain anchoring, or RBAC logic**, re-read the
relevant guardrail(s) above and:

1. Identify which numbered guardrail(s) govern the area you're changing.
2. Check the "Enforced at" file(s) for that guardrail and confirm your change doesn't
   route around them.
3. If your change affects hashing, geofence, RBAC, the lifecycle state machine, or the
   contract, add/update tests in the same change (Guardrail #11).
4. If you're unsure whether something is in scope, check `docs/GeoLegalVault_Project_Plan.md`
   before building it (Guardrail #12).
5. If you find a guardrail that code no longer matches, treat that as a bug — fix the code
   or explicitly flag the mismatch; don't silently update this file to match broken behavior.
