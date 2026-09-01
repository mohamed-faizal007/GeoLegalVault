# Software Requirements Specification — GeoLegalVault

**Geospatially-Aware Document Integrity & Lifecycle Platform (academic prototype).**
This SRS reflects the system as implemented (Phases 0–12). For architecture rationale and
trade-offs, see `GeoLegalVault_Project_Plan.md`; this document states requirements only.

## 1. Introduction

### 1.1 Purpose
Specify the functional and non-functional requirements of GeoLegalVault: a document
lifecycle platform that (a) enforces *where* sensitive operations may happen via
server-side geofencing, and (b) makes tampering with an approved document *detectable*
by anchoring each version's SHA-256 fingerprint on the Ethereum Sepolia testnet.

### 1.2 Intended audience
Evaluators/reviewers of the project, developers extending it, and anyone reproducing the
demo.

### 1.3 Definitions
- **Anchor** — an on-chain record `{documentId, version, sha256, eventType, timestamp}`.
- **Geofence** — an admin-defined GeoJSON polygon that a role's assigned operations are
  scoped to.
- **Version chain** — `document_versions` rows for one document, each carrying
  `prev_version_hash` pointing at the prior version's hash.
- **Tamper-evident** (not "tamper-proof") — a modification is *detectable* on the next
  Verify, not prevented from happening.

## 2. Scope

**In scope:** authentication/JWT, RBAC (5 roles, deny-by-default), geofence CRUD +
server-side enforcement, encrypted document upload/download, SHA-256 hashing, immutable
versioning, review/approval/amendment/archival workflow, blockchain anchoring on
approval, 3-way integrity verification, append-only audit log, admin/reporting UI, CI,
deployment to a free-tier cloud stack.

**Out of scope** (Plan Part 1.12): real-time collaborative editing, e-signatures/PKI
identity, OCR/NLP, mainnet deployment, native mobile apps, hardware GPS attestation,
multi-tenant billing, on-chain document storage, Merkle/hierarchical hashing (reserved
for a separate project).

## 3. Actors

| Role | Summary |
|---|---|
| Administrator | Manages users, geofences, views audit + reports. Cannot upload/review/approve (separation of duties). |
| Legal Officer | Uploads, amends, approves (triggers anchoring), verifies. |
| Reviewing Officer | Reviews submissions (approve-to-next-stage or request changes). |
| Authorized Staff | Uploads, amends, verifies. Cannot approve. |
| Auditor | Read-only everywhere; views the full audit log. |

Full permission matrix: `backend/app/core/rbac.py` (`ROLE_PERMISSIONS`), mirrored in
Plan Part 3.

## 4. Functional requirements

Each FR below is implemented; see the referenced module for the authoritative behavior.

| ID | Requirement | Module |
|---|---|---|
| FR-1 | Email+password login issues a short-lived JWT access token and a rotating httpOnly refresh cookie. | `modules/auth` |
| FR-2 | Only Admin provisions users (no self-registration). | `modules/users` |
| FR-3 | Refresh-token reuse revokes the whole session family. | `modules/auth` |
| FR-4 | Every protected endpoint declares a required permission; missing = 403, deny-by-default. | `core/rbac.py` |
| FR-5 | Admin lists/edits/deactivates users; hard-delete is never exposed. | `modules/users` |
| FR-6 | Admin manages GeoJSON polygon geofences with a 2dsphere index. | `modules/geofences` |
| FR-7 | Sensitive ops require server-recomputed point-in-polygon; low accuracy/staleness fail closed (422); outside-fence is 403. Client "allowed" flags are never trusted. | `services/geofence.py` |
| FR-8 | Upload validates size/MIME/magic bytes, stores server-side-keyed encrypted object, computes SHA-256, creates `documents` + V1 `document_versions`. Storage failure leaves no orphan metadata. | `modules/documents` |
| FR-9 | Download is a short-lived pre-signed URL; the API never proxies file bytes. | `modules/documents`, `services/storage.py` |
| FR-10 | Search/filter/paginate by title, tags, status, doc_type, owner, date range. | `modules/documents` |
| FR-11 | Core provenance fields (hash, storage key, version_no) are immutable once written. | `modules/versions` |
| FR-12 | Every content change creates a new version with `prev_version_hash`; prior versions are never mutated. | `modules/versions` |
| FR-13 | Reviewing Officer moves SUBMITTED → UNDER_REVIEW → PENDING_APPROVAL or CHANGES_REQUESTED (looping to DRAFT); reviewer ≠ uploader. | `modules/documents/workflow.py` |
| FR-14 | Legal Officer approval (approver ≠ uploader) auto-triggers anchoring of that version — never a user-triggered action. | `modules/documents/workflow.py` |
| FR-15 | Amendment creates DRAFT V(n+1) with `prev_version_hash` = current version's hash; on activation the prior ACTIVE version becomes SUPERSEDED (retained, still verifiable). | `modules/documents/workflow.py` |
| FR-16 | SHA-256 computed server-side on exact stored bytes, at upload and at every verify. | `services/hashing.py` |
| FR-17 | Approval sends `anchor(documentId, version, hash, eventType)` via the backend service wallet; tx hash/block recorded in `blockchain_anchors`. | `services/blockchain.py`, `modules/blockchain` |
| FR-18 | On-chain record is independently readable (`getAnchor`) and compared against the DB. | `modules/blockchain` |
| FR-19 | Verify recomputes SHA-256 from live storage bytes and 3-way-compares against stored + on-chain hash → VERIFIED / MISMATCH / NOT_ANCHORED, and records every check. | `modules/verify` |
| FR-20 | Every security-relevant action (login, upload, geofence denial, review/approve/anchor outcome, verify outcome, archive, …) is written to an append-only `audit_logs`, queryable by Auditor/Admin only. | `modules/audit` |
| FR-21 | In-app only — no email notifications (cut per the plan's "golden rule" priority list; not required for the MVP loop). |  |
| FR-22 | Admin panel: users, geofences, reports, system health. | frontend `AdminPanel.tsx` |
| FR-23 | `/reports/summary` aggregates counts by status/type, anchor success rate, recent verifications, geofence-denied counts. | `modules/reports` |
| FR-24 | Archival hides a document from the default repository list but retains every version and anchor; reachable via an explicit status filter. | `modules/documents` |

## 5. Non-functional requirements

| Category | Requirement |
|---|---|
| Security | TLS in transit (platform-terminated); Argon2id password hashing; JWT alg pinned (HS256), `none` rejected; deny-by-default RBAC; server-side-only geofence checks; private object storage with pre-signed URLs only; NoSQL queries built via the driver's typed filters (no raw `$where`/string interpolation); server-generated storage keys (no client filenames on disk); rate limiting (global + auth-specific); security response headers. See `THREAT_MODEL.md`. |
| Honesty in claims | No "military-grade," "tamper-proof," "unhackable," or "guaranteed location" wording anywhere in code, docs, or UI — "tamper-evident," "policy-level geofencing," "prototype-grade" only. |
| Availability | Modular monolith, stateless API process; async I/O throughout (Motor, httpx, web3.py calls off the event loop). Anchor/RPC failures never block the app — documents stay usable in an APPROVED(pending-anchor) state and retry. |
| Performance | Target latencies (Plan Part 22): non-chain API p95 < 500 ms; upload (≤10 MB) < 5 s; verify end-to-end < 3 s; blockchain confirmation is intentionally async (15 s–2 min) and never blocks the UI. Not load-tested at scale — this is a prototype. |
| Data integrity | `document_versions` is insert-only (one whitelisted status-update path); `audit_logs` is append-only (no update/delete API). |
| Portability | Runs identically via `docker-compose up` locally and via Render/Vercel/Atlas/R2/Sepolia in the cloud — the only difference is environment variables. |
| Observability | Structured JSON request logs; optional Sentry; `/api/v1/health` reports Mongo/storage/chain reachability. |
| Cost | ₹0 target — every dependency (Atlas M0, R2 free tier, Sepolia testnet, Render/Vercel free tiers) runs on a free plan. |

## 6. Constraints

- Backend: Python 3.11+, FastAPI, Motor (async MongoDB), Pydantic v2.
- Frontend: React + Vite + TypeScript + Tailwind + TanStack Query.
- Blockchain: Solidity 0.8.20 on Sepolia via Hardhat + web3.py; one custodial service wallet
  signs every anchor — there is no per-user MetaMask flow anywhere.
- Storage: any S3-compatible endpoint (Cloudflare R2 in production, MinIO in local dev).
- No Merkle trees, no NLP, no microservices/message brokers, no mainnet deployment
  (Guardrail #8).

## 7. Acceptance criteria

Mirrors the project's Global Definition of Done (Plan Part G / `IMPLEMENTATION_PROMPT.md`):
admin-provisioned login works; sensitive ops are blocked outside an authorized geofence
and allowed inside (demonstrated with two real locations); upload → encrypt → hash →
store metadata works; approval anchors on Sepolia with a resolvable Etherscan link;
amendment produces an independently verifiable V2 without destroying V1; Verify returns
VERIFIED for an untouched file and MISMATCH (live, in front of the reviewer) for a
tampered one; every security-relevant action appears in the audit log; RBAC is enforced
and tested per role; the 10-minute demo (`DEMO_SCRIPT.md`) runs end-to-end twice with no
manual database fixes; CI is green; documentation set is complete and free of overstated
security claims.
