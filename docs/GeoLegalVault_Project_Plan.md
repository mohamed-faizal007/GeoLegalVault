# GeoLegalVault — Production-Level Project Plan & Architecture

> **Geospatially-Aware Document Integrity & Lifecycle Platform (Academic Prototype)**
> Blockchain-anchored integrity · Off-chain encrypted storage · NoSQL metadata · Geofenced authorization
> Prepared as a delivery-owner engineering blueprint for a 2–4 person student team, ₹0 target budget.

---

## 0. READ THIS FIRST — Critical Analysis Before You Build Anything

You asked me not to blindly accept your architecture. I won't. Your core instincts are **correct**, but several assumptions will get you criticized in a viva or an interview if left unchallenged. Here is the honest triage.

### 0.1 What is genuinely good in your design

| Decision | Verdict | Why |
|---|---|---|
| Document off-chain, hash on-chain | ✅ Keep | This is the *only* defensible blockchain pattern. Storing documents on-chain is expensive, public, and immutable-in-a-bad-way (you can never delete leaked PII). |
| SHA-256 fingerprint | ✅ Keep | Standard, collision-resistant enough for integrity, cheap to compute. |
| MongoDB for metadata/versions/geofences | ✅ Keep | Flexible schema for evolving metadata + native geospatial (`2dsphere`) is a real, non-cosmetic reason to pick it. |
| Sepolia testnet, not mainnet | ✅ Keep | Free gas, no real money at risk. Correct for a student project. |
| Version history is immutable (no overwrite) | ✅ Keep | This is your strongest lifecycle feature. Enforce it hard. |
| RBAC + audit trail | ✅ Keep | Expected of any serious document system. |

### 0.2 What is technically weak or overclaimed — and the smallest fix

| Problem in your brief | Severity | Smallest correction |
|---|---|---|
| **"Military-grade" geofencing via browser GPS** | 🔴 Critical credibility risk | Browser Geolocation is **trivially spoofable** (DevTools sensor override, fake-GPS extensions, VPN+API tampering). Do **not** claim military security. Reframe as *"policy-based geospatial authorization, prototype-grade"* and document exactly what a real deployment would need (Part 11). This single reframing protects you in every review. |
| **Per-user MetaMask signing** | 🟠 Friction/feasibility | Requiring every officer to hold a wallet + testnet ETH + sign each anchor is unrealistic and blocks demos. Use a **single backend service wallet** (custodial anchoring). Recommended in Part 18. |
| **AWS S3 "prefer AWS"** | 🟠 Cost/bill-shock risk | S3 free tier **expires after 12 months** and misconfigured egress can generate surprise bills — a real risk for students. Recommend **Cloudflare R2** (10 GB free, **zero egress fees**, S3-compatible API) as primary, S3 as documented alternative. |
| **Merkle trees in Project 1** | 🟡 Scope creep | You said your TARP project owns hierarchical hashing/Merkle/NLP. **Keep Merkle out of Project 1.** Use document-level SHA-256 + a *version-chain hash* (each version stores previous version's hash) as a lightweight, distinct differentiator. Details in Part 13. |
| **Microservices / queues everywhere** | 🟡 Over-engineering | A **modular monolith** (FastAPI, one deployable) is correct at this scale. One optional background worker for blockchain confirmation polling — nothing more. |
| **Malware scanning as a hard requirement** | 🟡 Feasibility | Full AV scanning (ClamAV) is nice-to-have. MVP does MIME/type/size/magic-byte validation; ClamAV only if time permits. |
| **NLP** | 🟡 Unnecessary here | You listed NLP "if genuinely useful." It is **not** useful for Project 1 and belongs to TARP. Do not add it. |
| **Sepolia persistence assumption** | 🟡 Reliability | Testnets can reset/deprecate and RPC free tiers rate-limit. Always keep the tx hash + a local anchor record so a demo never depends on the chain being reachable live. |

### 0.3 The one-sentence honest positioning

> GeoLegalVault is a **cloud-native document integrity and lifecycle platform** that adds **geospatial policy enforcement** and **blockchain anchoring of cryptographic fingerprints** — an engineering integration project with one genuinely uncommon combination (geofenced document operations + on-chain integrity + immutable version lineage), **not** a military security product.

Everything below is written to that honest standard.

---

## PART 1 — Executive Project Definition

**1. Final recommended title:** *GeoLegalVault — Geospatially-Aware Document Integrity & Lifecycle Platform.* (Drop "Military." Keep "Geospatially-Aware" as the differentiator.)

**2. One-line description:** A secure web platform that manages the full lifecycle of sensitive documents, enforces where sensitive operations may occur, and proves each version was never tampered with by anchoring its cryptographic fingerprint to a public blockchain.

**3. Executive summary:** GeoLegalVault stores documents in encrypted cloud object storage, keeps rich metadata and immutable version lineage in MongoDB, computes a SHA-256 fingerprint of every version, and anchors that fingerprint (plus document ID, version, event type, timestamp) to an Ethereum Sepolia smart contract. Sensitive operations (upload, approve, amend, verify) are gated by three checks in sequence: **authentication (JWT) → role authorization (RBAC) → geospatial authorization (geofence)**. Any later reader can independently recompute a document's hash and compare it against the on-chain value to prove integrity. Every action is written to an append-only audit log.

**4. Problem being solved:** Organisations handling legal/controlled documents cannot easily prove, to a third party, that a stored document is byte-identical to what was officially approved — and they cannot restrict *where* sensitive operations happen. Existing DMS tools trust their own database; a database admin can silently alter a record.

**5. Why it matters:** Legal and compliance disputes turn on document integrity ("is this the version that was signed?"). Trust-me integrity ("our logs say so") is weak because the party asserting it also controls the logs. A tamper-evident, externally verifiable proof changes the trust model. Geographic policy adds a second control dimension relevant to controlled environments.

**6. Existing systems:** SharePoint/M365, Google Workspace, DocuWare, OpenKM, Alfresco, iManage. Plus blockchain-notary services (e.g., hash-timestamping tools).

**7. Problems with existing systems:** (a) Integrity is self-asserted — the vendor's DB is the source of truth. (b) No cryptographic proof verifiable by an outside party without trusting the vendor. (c) No native geospatial authorization of operations. (d) Notary-only tools timestamp a hash but have no lifecycle, RBAC, versioning, or access control around it. GeoLegalVault combines the DMS lifecycle *with* external verifiability *and* location policy.

**8. Proposed solution:** See executive summary. The novelty is the *combination and the enforcement pipeline*, not any single component.

**9. Target users:** Legal departments, compliance teams, records offices, contract-management units, any org needing verifiable document provenance with location-scoped operations. (Framed generically — no military claim.)

**10. Target use cases:** Contract lifecycle with tamper-proof approved versions; controlled-facility document access; audit/compliance evidence packages; dispute resolution ("prove this is the approved V2").

**11. Project scope (in):** Auth+RBAC, geofence CRUD + enforcement, document upload/download/search, immutable versioning, review/approval/amendment workflow, SHA-256 hashing, blockchain anchoring + verification, audit logging, admin panel, basic reporting, archival.

**12. Out of scope:** Real-time collaborative editing, e-signatures/PKI identity, OCR/full-text NLP, mainnet deployment, mobile native apps, real hardware GPS attestation, multi-tenant billing, on-chain document storage, Merkle/hierarchical hashing (reserved for TARP).

**13. Key differentiators:** (1) Three-gate enforcement pipeline (identity → role → location). (2) Externally verifiable integrity via public chain. (3) Immutable version lineage with per-version anchoring. (4) Geofence as a first-class, queryable policy object.

**14. Main novelty:** *Geospatial authorization of document lifecycle operations combined with per-version blockchain anchoring* — an uncommon integration, honestly framed as engineering novelty (Part 27).

**15. Expected final product — what a user can actually do:** Log in; the system detects their role and current location; if inside an authorized geofence they may upload a document (it is encrypted, stored, hashed, metadata saved, and after approval its fingerprint is anchored on-chain); browse/search a repository; open a document's full version history; request/perform an amendment that creates V2 without destroying V1; click "Verify" to see a live comparison of the current file's hash vs the on-chain hash with a green/red result and a link to the Sepolia transaction; and (as admin/auditor) inspect a complete audit trail.

---

## PART 2 — Requirements Engineering

### 2.1 Functional requirements (detailed for major features)

Format per feature: **Requirement / Actor / Preconditions / Main flow / Alternate / Failure / Security / DB impact / API impact.**

**FR-1 Authentication (Login)**
- **Requirement:** Users authenticate with email+password and receive a short-lived JWT access token + refresh token.
- **Actor:** All registered users.
- **Preconditions:** Account exists and is active.
- **Main flow:** Submit credentials → server verifies Argon2id hash → issues access JWT (~15 min) + refresh token (httpOnly cookie) → client stores access token in memory.
- **Alternate:** Refresh flow exchanges a valid refresh token for a new access token.
- **Failure:** Wrong password → 401 + generic message; locked/disabled account → 403; too many attempts → 429.
- **Security:** Argon2id, constant-time compare, rate limiting, no user-enumeration in error text, refresh token rotation.
- **DB impact:** Read `users`; write `audit_logs` (LOGIN_SUCCESS/FAILURE).
- **API:** `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`.

**FR-2 User registration** — Actor: Admin (self-registration is out of scope; officers are provisioned). Admin creates a user with role + optional home-unit geofence assignment. Failure: duplicate email → 409. Security: only Admin role; password set via one-time invite link if time permits, else admin-set temp password forcing reset. DB: insert `users`. API: `POST /api/v1/users`.

**FR-3 JWT/session management** — Access token carries `sub`, `role`, `iat`, `exp`, `jti`. No sensitive data in payload. Server keeps a refresh-token store to allow revocation. Expired/invalid token → 401. Reused/rotated refresh token → revoke session family (replay defense).

**FR-4 RBAC** — Every protected endpoint declares required permission; a dependency checks `role → permission` map. Missing permission → 403. Deny-by-default. DB: read role/permission map (can be code-config for MVP). See Part 3 matrix.

**FR-5 User management** — Admin lists/edits/deactivates users, assigns roles/geofences. Never hard-delete a user who owns documents (Part 35). API: `GET/PATCH /api/v1/users/{id}`.

**FR-6 Geofence management** — Admin creates named geofences as GeoJSON Polygons (or center+radius). Stored in `geofences` with `2dsphere` index. Validation: valid GeoJSON, closed ring, ≤ N vertices. API: `POST/GET/PATCH/DELETE /api/v1/geofences`.

**FR-7 Location verification** — On sensitive operations, client sends current `{lat,lng,accuracy,timestamp}`. Server runs a point-in-polygon `$geoIntersects` query against geofences the user's role/policy permits. Fail cases: outside all fences → 403 GEOFENCE_DENIED; accuracy worse than threshold → 422 LOCATION_LOW_CONFIDENCE; stale timestamp → 422. Security: server-side check only — **never trust a client "allowed=true" flag** (see Part 14).

**FR-8 Document upload** — Actor: roles with `upload`. Precondition: authenticated + in geofence. Flow: validate file (size/MIME/magic bytes) → stream to object storage (server-side encrypted) → compute SHA-256 → create `documents` + `document_versions` (V1, status DRAFT) → audit. Failure: invalid file → 422; storage down → 503 (transactional rollback, no orphan metadata). API: `POST /api/v1/documents`.

**FR-9 Document retrieval / download** — Authz + geofence check → generate a **short-lived pre-signed URL** (e.g., 60 s) → client fetches directly from storage. Never proxy large files through the app unless required. Audit every access. API: `GET /api/v1/documents/{id}`, `GET /api/v1/documents/{id}/download`.

**FR-10 Document search** — Filter by title, type, status, owner, date range, tags. Text index on title/tags; paginated. API: `GET /api/v1/documents?query=&status=&page=`.

**FR-11 Document metadata** — Structured fields (title, type, classification-label, owner, created/updated, current version, status) editable pre-approval only for mutable fields; core provenance fields immutable.

**FR-12 Version management** — Every content change creates a new immutable version doc with its own hash and a `prev_version_hash` pointer. Old versions never mutated. API: `GET /api/v1/documents/{id}/versions`.

**FR-13 Review workflow** — Reviewing Officer moves SUBMITTED → UNDER_REVIEW → (APPROVED or CHANGES_REQUESTED). Comments stored. Audit each transition.

**FR-14 Approval workflow** — Legal Officer (or designated approver) approves → triggers blockchain anchoring of that version. Only APPROVED versions get anchored (keeps gas usage bounded and semantically meaningful).

**FR-15 Amendment workflow** — Authorized user requests amendment on an ACTIVE doc → new DRAFT version (V(n+1)) created from a fresh upload → re-enters review → on approval, anchored → becomes ACTIVE; previous version becomes SUPERSEDED (not deleted).

**FR-16 Hash generation** — SHA-256 computed server-side on the exact stored bytes at upload and re-computed on verify. Stored in the version doc.

**FR-17 Blockchain anchoring** — Backend service wallet calls `anchor(documentId, version, sha256, eventType)` on the Sepolia contract; stores returned tx hash + block number in `blockchain_anchors`. Confirmation polled by a background worker. Failure handling in Part 5/12.

**FR-18 Blockchain verification** — Given a document version, backend reads the on-chain record and compares with the freshly computed hash. Returns MATCH / MISMATCH / NOT_ANCHORED with the tx link.

**FR-19 Integrity verification (end-to-end)** — Fetch stored bytes → recompute SHA-256 → compare to (a) stored hash and (b) on-chain hash. All three must agree for VERIFIED.

**FR-20 Audit logging** — Append-only log of every security-relevant action with actor, action, target, timestamp, IP, location, result. See Part 32.

**FR-21 Notifications** — MVP: in-app notification list for review/approval events. Email optional (nice-to-have) via a free provider.

**FR-22 Admin functionality** — Manage users, roles, geofences, view all audit logs, view system health.

**FR-23 Reporting** — Counts by status/type, anchoring success rate, recent verifications, access-denied events. Simple aggregation queries.

**FR-24 Archival** — ARCHIVED status hides docs from default views but retains all versions and anchors. Retention policy metadata recorded.

**FR-25 Deletion/retention** — Soft delete only for documents (status DELETED + retention timer). Hard delete forbidden for anchored versions (on-chain record is permanent anyway). Object-storage lifecycle rule can purge blobs after retention while metadata + anchor remain for auditability.

### 2.2 Non-functional requirements

| Category | Requirement (prototype-realistic) |
|---|---|
| Performance | API p95 < 500 ms excluding blockchain; upload of ≤10 MB < 5 s; geofence query < 50 ms; hashing 10 MB < 300 ms. |
| Availability | Best-effort; free-tier backend may cold-start. Blockchain anchoring is async so app stays responsive. Target 99% during demo windows. |
| Security | See Part 14. TLS everywhere, encryption at rest, Argon2id, least-privilege storage keys, secrets never in repo. |
| Scalability | Design supports horizontal scale (stateless API, indexed queries) but demo runs single instance. |
| Maintainability | Modular monolith, typed code, ≥60% test coverage on core services, OpenAPI docs. |
| Usability | Clear three-gate feedback (why an action was denied: role vs location vs auth). |
| Privacy | Minimise PII on-chain (only IDs/hashes go on-chain — never names or content). Classification labels enforced by RBAC. |
| Auditability | Every state change produces an immutable audit record; audit log queryable by admin/auditor only. |

---

## PART 3 — User Roles & Permissions

Five roles, deny-by-default, least privilege.

| Role | Upload | View | Search | Amend (request) | Review | Approve | Verify | Anchor(auto) | Manage Users | Manage Geofences | View Audit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Administrator** | ➖¹ | ✅ | ✅ | ➖ | ➖ | ➖ | ✅ | ➖ | ✅ | ✅ | ✅ |
| **Legal Officer** | ✅ | ✅ | ✅ | ✅ | ➖ | ✅ | ✅ | (triggers) | ❌ | ❌ | own actions |
| **Reviewing Officer** | ❌ | ✅ | ✅ | ➖ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | own actions |
| **Authorized Staff** | ✅² | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Auditor** | ❌ | ✅(read-only) | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ (all) |

¹ Admin manages the system, not the document workflow — separation of duties keeps a super-admin from silently approving documents. Give Admin verify+read but not approve. (You can merge if the team is small, but call out the trade-off.)
² Authorized Staff can upload drafts and request amendments but cannot approve — enforces maker/checker separation.

**Hard rules:**
- **Approval ≠ upload by same rule but same person is discouraged**: enforce that the approver of a version is not its uploader where the role allows both (maker-checker). Implement as a validation on the approve endpoint.
- **Auditor is read-only, everywhere** — cannot mutate any document, but sees everything including audit logs. This is your independent-oversight role.
- **Blockchain anchoring is never a manual user permission** — it is an automatic system consequence of APPROVED. This prevents "anchor spam" and keeps the on-chain meaning clean.

Each permission is a string (e.g., `document:upload`, `geofence:manage`). Roles map to permission sets in config for MVP; can move to the `permissions` collection later.

---

## PART 4 — Complete Business Workflow

### A. Normal successful workflow (happy path)

```
Register(by Admin) → Login(JWT) → Role resolved(Legal Officer)
   → Client obtains GPS {lat,lng,acc} → Server: JWT ok? → RBAC: upload? → Geofence: inside HQ polygon?
   → Upload PDF → validate(size/MIME/magic) → encrypt+store(R2) → SHA-256 → create documents + version V1(DRAFT)
   → Submit → UNDER_REVIEW → Reviewing Officer approves review → Legal Officer APPROVES
   → System anchors {docId,1,hash,APPROVED,ts} on Sepolia → store tx hash → status BLOCKCHAIN_ANCHORED → ACTIVE
   → Later: Authorized Staff (in geofence) downloads via pre-signed URL
   → Anyone with view: clicks Verify → recompute hash == stored == on-chain → VERIFIED ✅
   → Audit log written at every arrow.
```

### B. Failure / attack workflow

```
Attacker steals a JWT (XSS attempt blocked by httpOnly refresh + short access TTL) — access token expires in 15 min.
Attacker spoofs GPS via DevTools to appear inside geofence:
   → Server accepts coordinates it cannot physically verify (KNOWN LIMITATION, Part 11)
   → BUT: role check still blocks unauthorized operations; audit log records the location + IP mismatch;
     accuracy/velocity heuristics flag anomalies. Result: geofence is a policy control, not an anti-spoof control.
Attacker edits the stored blob directly in object storage (compromised key):
   → Next Verify recomputes hash → MISMATCH vs on-chain → tamper DETECTED, document flagged, alert raised.
Attacker edits MongoDB metadata to change the stored hash to match their tampered file:
   → On-chain hash is immutable → Verify still MISMATCH → tamper DETECTED. (This is the whole point of anchoring.)
Attacker deletes the on-chain record:
   → Impossible; events on a public chain cannot be deleted.
Blockchain RPC is down during approval:
   → Anchor job queued + retried; document sits in APPROVED (pending anchor); app stays usable; anchor completes on retry.
```

The takeaway you must state openly in the report: **geofencing is defense-in-depth policy, not a cryptographic guarantee; blockchain anchoring is the actual tamper-evidence guarantee.**

---

## PART 5 — Critical Legal Document Lifecycle (State Machine)

```
          create/upload
  ┌────────► DRAFT ──submit──► SUBMITTED ──assign──► UNDER_REVIEW
  │                                                     │
  │                          changes requested ◄────────┤
  │                                                     ▼ approve(review)
  │                                              PENDING_APPROVAL
  │                                                     │ approve(final)
  │                                                     ▼
  │                                                APPROVED ──anchor tx──► BLOCKCHAIN_ANCHORED
  │                                                     │ (auto on confirmation)
  │                                                     ▼
  │  amend request (new version)                     ACTIVE ──────────────────┐
  └──────────────◄───────── AMENDMENT_REQUESTED ◄──────┘                       │
                                   │ upload new bytes                          │ archive
                                   ▼                                           ▼
                              (new DRAFT V(n+1) ... same cycle)            ARCHIVED
   Previous ACTIVE version → SUPERSEDED (immutable, retained, still verifiable)
```

Per transition:

| Transition | Who triggers | Validation | DB change | Blockchain | Audit | If anchor tx fails |
|---|---|---|---|---|---|---|
| →DRAFT | Legal Officer / Authorized Staff | auth+role+geofence, file valid | insert `documents`+`document_versions`(V_n) | none | UPLOAD | n/a |
| DRAFT→SUBMITTED | owner | must have file+metadata | version.status=SUBMITTED | none | SUBMIT | n/a |
| SUBMITTED→UNDER_REVIEW | Reviewing Officer | reviewer≠uploader | status update | none | REVIEW_START | n/a |
| UNDER_REVIEW→PENDING_APPROVAL | Reviewing Officer | review complete | status update | none | REVIEW_PASS | n/a |
| →CHANGES_REQUESTED→DRAFT | Reviewing Officer | comment required | status update | none | CHANGES_REQ | n/a |
| PENDING_APPROVAL→APPROVED | Legal Officer | approver≠uploader, geofence | status=APPROVED | **enqueue anchor** | APPROVE | job queued/retried |
| APPROVED→BLOCKCHAIN_ANCHORED | System | tx confirmed ≥N blocks | write `blockchain_anchors` | tx mined | ANCHOR_OK | stays APPROVED(pending), retry ×k, then alert |
| →ACTIVE | System | anchor confirmed | doc.current_version=V_n, status ACTIVE | none | ACTIVATE | n/a |
| ACTIVE→AMENDMENT_REQUESTED | Legal Officer/Auth Staff | reason required | flag set | none | AMEND_REQ | n/a |
| (amend)→new DRAFT | as upload | new file | new version V(n+1), prev_hash link | none (until approved) | UPLOAD | n/a |
| ACTIVE/SUPERSEDED→ARCHIVED | Admin/Legal Officer | retention ok | status=ARCHIVED | none | ARCHIVE | n/a |

**Versioning (V1, V2, V3):** each version is a separate immutable document in `document_versions` with `{version_no, sha256, prev_version_hash, storage_key, anchored_tx}`. Amendment never overwrites — it appends V(n+1) and marks V(n) SUPERSEDED. `documents.current_version_id` points at the active one. Full lineage is reconstructable and each version independently verifiable against its own on-chain anchor. This immutable lineage is a headline feature — protect it with a DB-level rule: version docs are insert-only; updates limited to a `status` field via a whitelisted service method.

---

## PART 6 — Realistic Scenarios (end to end)

Pipeline shorthand for each: **UI → API → AuthN → AuthZ → Geofence → DB → Cloud → Hash → Chain → Result**

**Scenario 1 — Legal Officer uploads a new contract.**
UI: fills form, browser prompts for location. → `POST /documents` with file + `{lat,lng,acc}`. → JWT valid, role=Legal Officer. → RBAC `document:upload` ✅. → Geofence: `$geoIntersects` HQ polygon → inside ✅. → validate file (PDF, 3 MB, magic bytes ok). → stream to R2 (SSE-encrypted), key `docs/{uuid}/v1`. → SHA-256 = `a1b2…`. → insert `documents` + `document_versions` V1 DRAFT with hash. → (not yet anchored). → Result: 201, doc in "My Drafts."

**Scenario 2 — Authorized user accesses a document from an approved location.**
UI: clicks Download. → `GET /documents/{id}/download` + location. → JWT ok, role=Authorized Staff. → RBAC `document:view` ✅. → Geofence inside ✅. → read metadata, check status ACTIVE. → generate 60 s pre-signed R2 URL. → (hash not needed for read). → audit ACCESS. → Result: browser downloads directly from storage; audit shows who/when/where.

**Scenario 3 — Access attempt from outside the geofence.**
UI: Download from a café. → same call. → JWT ok, RBAC ok. → Geofence: point not in any permitted polygon → `$geoIntersects` empty. → **403 GEOFENCE_DENIED**, no pre-signed URL issued, nothing read from storage. → audit ACCESS_DENIED with coordinates. → Result: clear message "Operation not permitted from your current location."

**Scenario 4 — Legitimate amendment.**
UI: Legal Officer opens ACTIVE contract → "Request Amendment" (reason). → `POST /documents/{id}/amend`. → auth+role+geofence ✅. → creates AMENDMENT_REQUESTED flag → officer uploads corrected PDF → new version V2 DRAFT, `prev_version_hash = V1.sha256`. → review → approve → anchor V2 → V2 ACTIVE, **V1 SUPERSEDED but retained + still verifiable**. → Result: version history shows V1 (superseded, verified) and V2 (active, verified), each with its own Sepolia tx.

**Scenario 5 — Someone modifies a document outside the authorized workflow (attack).**
Attacker with a leaked storage key overwrites the V2 blob. → later, any user clicks **Verify** on V2. → `POST /verify/{versionId}`. → backend fetches current bytes from R2 → recompute SHA-256 = `zz99…` → compare to stored hash `a1b2…` and on-chain hash `a1b2…` → **MISMATCH**. → Result: big red "INTEGRITY FAILED — file does not match approved version," document auto-flagged TAMPERED, alert to Admin/Auditor, audit VERIFY_FAIL. This is the demo money-shot.

---

## PART 7 — System Architecture

### A. Logical architecture (horizontal, PPT-friendly)

```
┌──────────────┐   HTTPS   ┌───────────────────────────── Backend (FastAPI modular monolith) ─────────────────────────────┐
│   Frontend   │ ───────►  │  API Gateway/Router → Auth ─ RBAC ─ Geofence ─ DocProcessing ─ Hashing ─ Version ─ Audit ─ BC │
│  React (SPA) │  ◄─────── │        │            │        │         │            │           │         │        │         │
└──────────────┘   JSON    └────────┼────────────┼────────┼─────────┼────────────┼───────────┼─────────┼────────┼─────────┘
                                     ▼            ▼        ▼         ▼            ▼           ▼         ▼        ▼
                                 [MongoDB Atlas]  [ ]   [2dsphere]  [R2/S3]   [SHA-256]  [versions] [audit] [Sepolia RPC]
                                                                                                                │
                                                                                              ┌─────────────────▼─────────┐
                                                                                              │ Smart Contract (Solidity) │
                                                                                              └───────────────────────────┘
                            (optional) Background Worker ── polls tx confirmations ── updates MongoDB
```

### B. Physical / deployment architecture

```
[User Browser] ──HTTPS──► [Vercel/Netlify: React static]
                                   │ calls
                                   ▼
                        [Render/Railway/Fly: FastAPI container] ──► [MongoDB Atlas M0]
                                   │                              └─► [Cloudflare R2 bucket]
                                   ├──► [Alchemy/Infura Sepolia RPC] ──► [Sepolia network + Contract]
                                   └──► [Background worker (same host or scheduled)]
   Secrets: platform env vars / .env (never in git).  Logs: platform log stream + Sentry(free).
```

### C. Data-flow architecture (upload)

```
bytes ─► validate ─► encrypt+store(R2, key) ─► SHA-256(bytes) ─► metadata+hash → MongoDB
                                                     └─(on approve)─► anchor(hash) → Sepolia → tx hash → MongoDB
```

### D. Security architecture (layers)

```
TLS ──► JWT verify ──► RBAC (deny by default) ──► Geofence check ──► Input/file validation ──► Least-priv storage key
                                                                                 │
   Encryption at rest (R2 SSE + Mongo Atlas encryption) · Argon2id passwords · Audit append-only · Secrets in vault/env
```

### E. Blockchain architecture

```
FastAPI BlockchainService ─signs with SERVICE WALLET (key in secret store)─► Sepolia RPC ─► DocumentAnchor.sol
   emits AnchorCreated(docId, version, hash, eventType, ts) ─► tx hash+block ─► MongoDB blockchain_anchors
Verification: read hash from contract mapping (or event logs) ─► compare with recomputed SHA-256.
```

---

## PART 8 — Technology Stack

Format: **Tech — why needed / what it does / why preferred / free? / alternative / complexity / risk.**

| Layer | Recommended | Why / What | Free? | Alternative | Complexity | Risk |
|---|---|---|---|---|---|---|
| Frontend | **React + Vite + TypeScript + Tailwind** | SPA, typed, fast dev, clean UI | Yes (MIT) | Next.js (overkill), Vue | Low–Med | Low |
| Backend | **Python + FastAPI** | async, auto OpenAPI, easy blockchain libs, fast to write | Yes | Node/Express, Django | Low–Med | Low |
| Auth | **JWT (PyJWT) + Argon2id (passlib/argon2)** | stateless auth + strong password hash | Yes | Auth0(free tier) | Low | Med (token handling) |
| Database | **MongoDB (Atlas M0)** | flexible metadata + native geospatial | Yes (M0 free forever, 512MB) | PostgreSQL+PostGIS | Med | Low |
| Object storage | **Cloudflare R2** | S3-API, 10GB free, **no egress fees** → no bill shock | Yes | AWS S3 (free 12mo), Backblaze B2 | Low | Low |
| Blockchain | **Ethereum Sepolia** | free testnet, EVM, huge tooling | Yes | Polygon Amoy testnet | Med | Med (faucets, RPC limits) |
| Smart contract | **Solidity + Hardhat** | standard EVM dev, tests, deploy scripts | Yes | Foundry | Med | Med |
| Web3 (backend) | **web3.py** | sign+send tx, read contract | Yes | ethers.js (if Node) | Med | Med |
| Doc processing | **python-magic + Pillow(if imgs) + pypdf(validate)** | MIME/magic-byte checks, PDF sanity | Yes | filetype lib | Low | Low |
| Geospatial | **MongoDB 2dsphere + GeoJSON**; **Turf.js** (client hints) | point-in-polygon, distance | Yes | PostGIS, Shapely | Med | Med (accuracy) |
| Malware scan (opt) | **ClamAV** | AV scan uploads | Yes | VirusTotal API(free-limited) | Med | Med |
| Testing | **pytest, httpx, Vitest/RTL, Hardhat tests** | unit/integration/e2e | Yes | Jest | Low–Med | Low |
| CI/CD | **GitHub Actions** | lint+test+build on PR | Yes (free minutes) | GitLab CI | Low | Low |
| Containers | **Docker + docker-compose** | reproducible dev env | Yes | Podman | Low–Med | Low |
| Monitoring/errors | **Sentry (free) + platform logs** | error tracking | Yes | self-host Grafana(heavy) | Low | Low |
| API docs | **FastAPI OpenAPI/Swagger UI** | auto-generated | Yes | Redoc | None | Low |
| Frontend host | **Vercel / Netlify** | free static hosting, HTTPS | Yes | Cloudflare Pages | Low | Low |
| Backend host | **Render / Railway / Fly.io** | free tier container | Yes/limited | local for demo | Low | Med (cold starts/quota) |

**NLP: deliberately excluded** (reserved for TARP, not useful here). **Merkle trees: excluded** (Part 13). No message queue beyond one optional lightweight worker.

---

## PART 9 — Cloud Architecture

### Components & choices
- **Object storage:** Cloudflare R2 private bucket, server-side encryption, no public access, all access via short-lived pre-signed URLs. (AWS S3 documented as the "prefer AWS" alternative with identical pattern: private bucket + IAM least-privilege + SSE-S3/KMS + pre-signed URLs + `BlockPublicAccess`.)
- **IAM / keys:** one storage access key with a scoped policy (put/get on one bucket/prefix only). Rotate. Never in frontend, never in git.
- **Encryption:** in transit TLS 1.2+; at rest SSE (R2/S3) + MongoDB Atlas encryption-at-rest (on by default).
- **Backend compute:** container on Render/Railway (free) for demo; local Docker for dev. EC2/serverless documented as the AWS-equivalent but not required (cost + ops overhead).
- **Secrets:** platform env vars; local `.env` (gitignored); optionally Doppler/1Password free for the team.
- **Networking:** backend public endpoint over HTTPS; DB via Atlas SRV connection string with IP allow-list + strong user; storage private.
- **Logging/monitoring:** platform log stream + Sentry; health check endpoint.
- **Backup:** Atlas automated snapshots (M0 limited — script a `mongodump` to a second free store weekly); R2 object versioning on.
- **DR:** documented (Part 31).
- **Cost control:** R2 no-egress removes the #1 student bill risk; billing alerts if AWS used; hard cap on file size; testnet only.

### Which is cloud vs local
| Env | Frontend | Backend | DB | Storage | Chain |
|---|---|---|---|---|---|
| **Development** | local Vite | local Docker | local Mongo (compose) or Atlas M0 | R2 dev bucket or local MinIO | Hardhat local node |
| **Testing/CI** | build in CI | CI container | ephemeral Mongo (test container) | MinIO/mock | Hardhat + Sepolia for integration |
| **Demo/Prod-like** | Vercel | Render/Railway | Atlas M0 | R2 prod bucket | Sepolia |

### ₹0 student strategy
All of: Atlas M0 (free forever) + R2 free tier + Sepolia (free) + Vercel + Render free + GitHub Actions free minutes + Sentry free = **₹0**. Only cost risk is exceeding free quotas → mitigations: small files, cleanup jobs, single instance, testnet.

---

## PART 10 — MongoDB / NoSQL Design

**Why MongoDB over PostgreSQL here (non-cosmetic reasons):** (1) **Native geospatial** — `2dsphere` + `$geoIntersects`/`$geoWithin`/`$near` give point-in-polygon and distance queries out of the box; PostGIS does this too but adds an extension + heavier ops. (2) **Evolving, heterogeneous metadata** — different document types carry different fields; a flexible schema avoids constant migrations during a fast student build. (3) **Embedded audit/version detail** reads naturally as documents. Be honest in the report: Postgres+PostGIS is a valid alternative; you chose Mongo for geospatial ergonomics + schema flexibility during rapid iteration, and you enforce integrity in the app layer + on-chain, not via SQL constraints.

### Collections

**`users`** — accounts. Fields: `_id, email(unique), password_hash, name, role, assigned_geofence_ids[], is_active, created_at, last_login`. Index: unique `email`, `role`. Security: never return `password_hash`; Argon2id.
```json
{"_id":"u_01","email":"officer@org.test","password_hash":"$argon2id$...","name":"A. Rao","role":"LEGAL_OFFICER","assigned_geofence_ids":["gf_hq"],"is_active":true,"created_at":"2026-01-10T09:00:00Z"}
```

**`documents`** — logical document. Fields: `_id, title, doc_type, classification, owner_id, status, current_version_id, tags[], created_at, updated_at, retention_until`. Index: `status`, `owner_id`, text index on `title,tags`, compound `{status:1, doc_type:1}`.
```json
{"_id":"d_100","title":"Vendor NDA","doc_type":"CONTRACT","classification":"RESTRICTED","owner_id":"u_01","status":"ACTIVE","current_version_id":"v_2","tags":["nda","vendor"],"created_at":"2026-01-11T10:00:00Z"}
```

**`document_versions`** — immutable versions (insert-only). Fields: `_id, document_id, version_no, sha256, prev_version_hash, storage_key, size_bytes, mime, status, uploaded_by, uploaded_at, anchored, anchor_id`. Index: compound `{document_id:1, version_no:1}` unique, `sha256`.
```json
{"_id":"v_2","document_id":"d_100","version_no":2,"sha256":"a1b2c3...","prev_version_hash":"9f8e7d...","storage_key":"docs/d_100/v2","size_bytes":312044,"mime":"application/pdf","status":"ACTIVE","uploaded_by":"u_01","uploaded_at":"2026-02-01T08:00:00Z","anchored":true,"anchor_id":"bc_55"}
```

**`geofences`** — GeoJSON polygons. Fields: `_id, name, region(GeoJSON Polygon), radius_m?, active`. Index: **`2dsphere` on `region`**.
```json
{"_id":"gf_hq","name":"HQ Campus","active":true,"region":{"type":"Polygon","coordinates":[[[78.14,11.66],[78.16,11.66],[78.16,11.68],[78.14,11.68],[78.14,11.66]]]}}
```

**`permissions`** — (optional; code-config for MVP) role→permission map. Index: `role`.

**`audit_logs`** — append-only. Fields: `_id, actor_id, action, target_type, target_id, result, ip, location(GeoJSON Point), meta, created_at`. Index: `{actor_id:1, created_at:-1}`, `action`, `2dsphere` on `location`. Consider a capped or time-series collection.
```json
{"_id":"a_9001","actor_id":"u_01","action":"VERIFY_FAIL","target_type":"version","target_id":"v_2","result":"MISMATCH","ip":"1.2.3.4","location":{"type":"Point","coordinates":[78.15,11.67]},"created_at":"2026-02-03T12:00:00Z"}
```

**`blockchain_anchors`** — Fields: `_id, document_id, version_id, sha256, event_type, tx_hash, block_number, contract_address, network, status(PENDING/CONFIRMED/FAILED), created_at, confirmed_at`. Index: `tx_hash` unique, `{version_id:1}`.
```json
{"_id":"bc_55","document_id":"d_100","version_id":"v_2","sha256":"a1b2c3...","event_type":"APPROVED","tx_hash":"0xabc...","block_number":5123456,"network":"sepolia","status":"CONFIRMED","created_at":"2026-02-01T08:05:00Z"}
```

**`verification_records`** — Fields: `_id, version_id, requested_by, recomputed_hash, stored_hash, onchain_hash, result(VERIFIED/MISMATCH/NOT_ANCHORED), created_at`. Index: `{version_id:1, created_at:-1}`.

### Geospatial query examples
```js
// Is the user inside ANY geofence they're assigned to?
db.geofences.findOne({
  _id: { $in: user.assigned_geofence_ids },
  active: true,
  region: { $geoIntersects: { $geometry: { type: "Point", coordinates: [lng, lat] } } }
})
// Distance-based (radius fence): points within 500m of a center
db.geofences.find({ center: { $near: { $geometry: {type:"Point",coordinates:[lng,lat]}, $maxDistance: 500 } } })
```
**Note:** GeoJSON is **[longitude, latitude]** order — a classic bug source; validate on input.

---
## PART 11 — Geolocation / Geofencing (with honest limits)

**How location is obtained:** browser `navigator.geolocation.getCurrentPosition()` → `{latitude, longitude, accuracy(m), timestamp}`. Sent to backend with each sensitive request. Backend runs the point-in-polygon check server-side.

**Limitations & risks (state these plainly):**
- **Browser geolocation is not trustworthy for security.** It can be overridden in DevTools (Sensors → Location), by browser extensions, by OS-level fake-GPS, or by tampering with the API payload before it reaches the server. Accuracy varies wildly (5 m GPS to 5 km IP-based).
- **GPS spoofing** is trivial for a motivated user. Therefore geofencing here is a **policy/defense-in-depth control**, not an anti-adversary guarantee.
- **Accuracy radius:** reject if `accuracy > threshold` (e.g., 100 m) → `LOCATION_LOW_CONFIDENCE`. A large accuracy radius means the point could be inside or outside the fence — treat as fail-closed.
- **Freshness:** reject if `timestamp` older than e.g. 60 s (prevents replay of an old "good" location).
- **Permission denied:** operation blocked with a clear message; user cannot perform geofenced actions without granting location. (Read-only, non-sensitive actions can still work if policy allows.)
- **Poor accuracy:** fail-closed for sensitive ops.
- **Spoofing detected/suspected:** you cannot cryptographically detect it from the browser. You can add heuristics: implausible velocity between requests, mismatch between GPS point and IP geolocation, repeated exact coordinates. Log and flag, don't claim prevention.

**Server-side check (never client-trusted):**
```
point = [lng, lat] from request
if accuracy > 100: return 422 LOW_CONFIDENCE
if now - timestamp > 60s: return 422 STALE
fence = geofences.$geoIntersects(point) within user's assigned fences
if not fence: return 403 GEOFENCE_DENIED
proceed
```

**Is browser GPS sufficient for a "military-grade" claim? NO.** Say this explicitly in the report. A real controlled-environment deployment would require some combination of: hardware GPS with anti-spoof/authentication (e.g., signed GNSS), device attestation (TPM/secure enclave), managed devices via MDM, network-based location (carrier/Wi-Fi RTT), physical access control integration, and mutual-TLS client certificates. Your project is an **academic prototype demonstrating the geofenced-authorization pattern**, and framing it that way is a strength (you understood the threat model), not a weakness.

---

## PART 12 — Blockchain Architecture

**Why blockchain at all (justify honestly):** you need integrity proof that is verifiable by a third party *without trusting your own database/admins*. A public chain gives an append-only, tamper-evident, independently-readable record. If the only requirement were "detect tampering for ourselves," a signed hash in a DB would do — blockchain adds the *external, un-deletable* trust anchor. State this trade-off; don't pretend blockchain is the only option.

**Why Ethereum / why Sepolia:** biggest EVM tooling ecosystem (Hardhat, web3.py, explorers), and Sepolia is a stable, free, well-supported testnet with working faucets → ₹0. (Polygon Amoy is a fine alternative.)

**On-chain (minimal):** `documentId (bytes32/string)`, `version (uint)`, `sha256 hash (bytes32)`, `eventType (enum/uint8)`, `timestamp (block)`. **Off-chain:** the document, all metadata, names, content — everything confidential. **Never** put document bytes or PII on-chain.

**Wallet architecture:** one **backend service wallet** (custodial). Its private key lives only in the backend secret store, never in frontend/git. It pays gas with faucet Sepolia ETH. Rationale + safer alternative in Part 18.

**Transaction lifecycle:** build tx → sign with service key → send to Sepolia RPC → receive tx hash (pending) → background worker polls until ≥N confirmations → mark CONFIRMED + store block number. On revert/timeout → FAILED → retry with backoff → after k retries → alert; document stays APPROVED(pending anchor), app remains usable.

**Failure handling:** RPC down → queue + retry. Out of testnet ETH → alert to top up from faucet. Nonce collision → serialize anchoring (single worker) or manage nonce. Tx stuck → bump gas/re-send.

**Immutability & limitations:** on-chain record can't be altered/deleted — that's the guarantee. Limitations: chain only proves *"this hash existed at this time under this docId/version"*; it does **not** prove the off-chain file is authentic authorship or that the uploader was honest — it proves the file hasn't changed since anchoring. Testnets can reset/deprecate (keep tx records locally; consider re-anchoring capability).

### Minimal smart contract (Solidity, illustrative)
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract DocumentAnchor {
    address public owner;                 // backend service wallet
    mapping(address => bool) public writers; // allowed anchoring accounts

    struct Anchor { bytes32 hash; uint32 version; uint8 eventType; uint64 ts; bool exists; }
    // key = keccak256(documentId, version)
    mapping(bytes32 => Anchor) private anchors;

    event AnchorCreated(string documentId, uint32 version, bytes32 hash, uint8 eventType, uint64 ts);

    modifier onlyWriter() { require(writers[msg.sender], "not authorized"); _; }
    constructor() { owner = msg.sender; writers[msg.sender] = true; }
    function setWriter(address a, bool ok) external { require(msg.sender==owner,"only owner"); writers[a]=ok; }

    function anchor(string calldata documentId, uint32 version, bytes32 hash, uint8 eventType) external onlyWriter {
        bytes32 key = keccak256(abi.encodePacked(documentId, version));
        require(!anchors[key].exists, "already anchored"); // immutability per (doc,version)
        anchors[key] = Anchor(hash, version, eventType, uint64(block.timestamp), true);
        emit AnchorCreated(documentId, version, hash, eventType, uint64(block.timestamp));
    }
    function getAnchor(string calldata documentId, uint32 version)
        external view returns (bytes32 hash, uint8 eventType, uint64 ts, bool exists) {
        Anchor storage a = anchors[keccak256(abi.encodePacked(documentId, version))];
        return (a.hash, a.eventType, a.ts, a.exists);
    }
}
```
**Access control:** `onlyWriter` (service wallet). **Validation:** reject re-anchoring same (doc,version) → enforces one immutable record per version. **Gas considerations:** one small `SSTORE` + event ≈ cheap; strings cost more than bytes32 — you may hash the documentId to `bytes32` to save gas. **Security risks:** service-key compromise → attacker could anchor false records (mitigate: key in secret store, minimal funds, rotate; the app cross-checks stored vs recomputed vs on-chain so a false anchor alone doesn't corrupt an existing verified doc). Don't over-engineer: no upgradeability proxy, no tokens, no complex roles.

---

## PART 13 — Cryptographic Design

- **SHA-256:** one-way, collision-resistant fingerprint of exact stored bytes. Chosen because it's standard, fast, widely trusted, and fits `bytes32` on-chain.
- **Why hashing:** a 32-byte hash uniquely represents an arbitrarily large file; comparing hashes proves byte-identity without re-sending the file.
- **Timing:** compute at upload (on the exact bytes written to storage) and again at every verify (on bytes read back). Anchor the upload-time hash at approval.
- **If a document changes (even 1 byte):** hash changes completely (avalanche effect) → verify → MISMATCH.
- **Comparison:** constant-time compare of recomputed vs stored vs on-chain.
- **Collisions:** SHA-256 has no known practical collisions; adequate for this project. (Note MD5/SHA-1 are broken — don't use them.)
- **Version hashes:** each version hashed independently; store `prev_version_hash` to form a **version chain** (V2 records V1's hash). This gives tamper-evident lineage cheaply.

**Merkle trees — include or defer?** **Defer to TARP.** Your TARP owns hierarchical hashing / Merkle / NLP tamper-localization. To keep Project 1 distinct and avoid overlap: **Project 1 uses document-level SHA-256 + a linear version-chain hash only.** That version chain is a *light* form of structural integrity that is clearly simpler than TARP's intra-document Merkle localization, so the two projects stay technically separate and you can defend the boundary in a viva: *"Project 1 proves whole-document + version-lineage integrity; TARP localizes tampering within a document using hierarchical hashing/NLP."*

---

## PART 14 — Security Architecture (Threat Model)

Format: **Threat → Impact → Likelihood → Mitigation → Residual risk.**

| # | Threat | Impact | Likelihood | Mitigation | Residual |
|---|---|---|---|---|---|
| 1 | Credential theft / weak passwords | Account takeover | Med | Argon2id, min-strength policy, rate limit, lockout | Low |
| 2 | JWT theft (XSS) | Impersonation | Med | Short access TTL, refresh in httpOnly cookie, CSP, sanitise inputs | Low-Med |
| 3 | JWT forgery/alg confusion | Full bypass | Low | Verify signature, pin alg (HS256/RS256), reject `none` | Low |
| 4 | Privilege escalation | Unauthorized ops | Med | Deny-by-default RBAC, server-side role from DB not token claims alone for sensitive ops | Low |
| 5 | IDOR (guess doc IDs) | Data exposure | Med | Authorization check per object, UUIDs, ownership/geofence checks | Low |
| 6 | Broken access control | Wide exposure | Med | Central authz layer, tests for every endpoint×role | Low |
| 7 | Malicious file upload | Malware distribution | Med | MIME+magic-byte+size validation, store non-executable, (opt) ClamAV, never serve inline | Med |
| 8 | Path traversal in keys/filenames | Overwrite/leak | Low | Generate storage keys server-side (UUIDs), never use client filename as path | Low |
| 9 | Object-storage misconfig (public bucket) | Mass leak | Med | Private bucket, BlockPublicAccess, pre-signed URLs only, key least-priv | Low |
| 10 | NoSQL injection | Data leak/bypass | Med | Parameterised queries via driver, validate/coerce types, no `$where`/user-built operators | Low |
| 11 | API abuse / brute force | DoS, cred stuffing | Med | Rate limiting, throttling, captchas on auth (opt) | Med |
| 12 | Replay attacks | Repeated ops | Low | Nonces/idempotency keys, location freshness, HTTPS | Low |
| 13 | Blockchain service-key compromise | False anchors | Low | Key in secret store, minimal funds, rotate, cross-verify vs stored+recomputed | Med |
| 14 | GPS spoofing | Geofence bypass | High | Fail-closed on accuracy/staleness, heuristics, log/flag; **acknowledged prototype limit** | High (accepted) |
| 15 | Geofence bypass via client flag | Bypass | Med | **Never trust client authorization result**; server-side check only | Low |
| 16 | DB tampering (admin/insider) | Silent alteration | Med | On-chain hash makes tampering detectable on verify; append-only audit | Low (detectable) |
| 17 | Cloud/account compromise | Broad | Low | MFA on cloud accounts, least-priv, separate keys | Med |
| 18 | Insider threat | Misuse | Med | Maker-checker separation, Auditor role, immutable audit + on-chain | Med |
| 19 | Audit log manipulation | Cover tracks | Med | Append-only/time-series collection, restricted writes, periodic hash of log batches (opt) | Low-Med |
| 20 | Secrets in git | Full compromise | Med | `.gitignore`, secret scanning (GitHub), pre-commit hooks, env vars | Low |

**Cross-cutting:** OWASP API Top-10 checklist applied (broken object/function-level authz, excessive data exposure, injection, misconfig). Secrets management via env/vault. TLS in transit. Encryption at rest (storage SSE + Atlas). Argon2id passwords. Rate limiting (slowapi/nginx). Input validation (Pydantic). File scanning (validation now, ClamAV optional). Audit logging comprehensive.

---
## PART 15 — API Design (REST)

Base: `/api/v1`. Auth via `Authorization: Bearer <access>`. Errors as JSON `{"error":{"code":"GEOFENCE_DENIED","message":"...","details":{}}}`. Status codes: 200/201 success, 400 validation, 401 auth, 403 authz/geofence, 404 not found, 409 conflict, 422 semantic (bad location), 429 rate limit, 503 dependency down. Pagination `?page=&limit=` → `{items, page, total}`. Versioned via URL prefix.

| Method | Path | Auth | Role | Purpose |
|---|---|---|---|---|
| POST | /auth/login | No | any | login → tokens |
| POST | /auth/refresh | cookie | any | new access token |
| POST | /auth/logout | Yes | any | revoke session |
| GET | /users | Yes | Admin | list users |
| POST | /users | Yes | Admin | create user |
| PATCH | /users/{id} | Yes | Admin | update/deactivate |
| GET | /geofences | Yes | Admin/Auditor | list |
| POST | /geofences | Yes | Admin | create |
| PATCH/DELETE | /geofences/{id} | Yes | Admin | edit/deactivate |
| POST | /documents | Yes | upload roles | upload (multipart + location) |
| GET | /documents | Yes | view roles | search/list |
| GET | /documents/{id} | Yes | view | metadata |
| GET | /documents/{id}/download | Yes | view + geofence | pre-signed URL |
| GET | /documents/{id}/versions | Yes | view | version history |
| POST | /documents/{id}/submit | Yes | owner | submit for review |
| POST | /documents/{id}/review | Yes | Reviewing Officer | review decision |
| POST | /documents/{id}/approve | Yes | Legal Officer + geofence | approve → anchor |
| POST | /documents/{id}/amend | Yes | Legal Officer/Auth Staff | start amendment |
| POST | /documents/{id}/archive | Yes | Admin/Legal Officer | archive |
| POST | /verify/{versionId} | Yes | verify roles | integrity check |
| GET | /blockchain/anchor/{versionId} | Yes | view | on-chain record + tx link |
| GET | /audit | Yes | Auditor/Admin | query audit logs |
| GET | /health | No | — | health check |

**Examples**
```http
POST /api/v1/documents  (multipart)
fields: file=@nda.pdf; title=Vendor NDA; doc_type=CONTRACT; lat=11.67; lng=78.15; accuracy=25
→ 201 {"document_id":"d_100","version_id":"v_1","status":"DRAFT","sha256":"a1b2..."}
→ 403 {"error":{"code":"GEOFENCE_DENIED","message":"Operation not permitted from your current location"}}

POST /api/v1/verify/v_2
→ 200 {"result":"VERIFIED","recomputed":"a1b2...","stored":"a1b2...","onchain":"a1b2...","tx":"0xabc..."}
→ 200 {"result":"MISMATCH","recomputed":"zz99...","stored":"a1b2...","onchain":"a1b2...","tx":"0xabc..."}
```

---

## PART 16 — Frontend Product Design

Stack: React + Vite + TS + Tailwind + React Router + a data layer (TanStack Query). Access token in memory; refresh via cookie. Global "location gate" component requests geolocation before sensitive actions.

| Page | Purpose | Key components | Actions | API | Data shown | Validation/errors | Security |
|---|---|---|---|---|---|---|---|
| Login | authenticate | form | submit | /auth/login | — | invalid creds, 429 | no enumeration |
| Dashboard | overview | cards, role badge, location status | navigate | /documents, /audit summary | counts, my drafts, geofence status | — | role-scoped widgets |
| Document Repository | browse/search | table, filters, pagination | search/open | /documents | list | empty/error states | only permitted docs |
| Upload | create doc | dropzone, metadata form, location gate | upload | POST /documents | progress | size/MIME, geofence-denied | client+server validate |
| Document Details | view one | metadata, status, verify button | download/verify/amend | /documents/{id}, /verify | version, hashes | not-found, denied | pre-signed only |
| Version History | lineage | timeline, per-version verify + tx link | verify | /versions, /blockchain | V1..Vn, superseded flags | — | read-scoped |
| Amendment Request | amend | reason + upload | submit | /amend, /documents | current version | reason required | role+geofence |
| Verification | integrity | big status, 3-way hash compare, tx link | run verify | /verify | VERIFIED/MISMATCH | — | audited |
| Geofence Status | show location result | map, in/out badge, accuracy | refresh location | — | current point vs fence | permission denied | — |
| Audit Logs | oversight | filterable table | filter/export | /audit | actor/action/result | — | Auditor/Admin only |
| Blockchain Verification | chain view | tx hash, block, Etherscan link | open explorer | /blockchain | anchor record | not anchored | read-only |
| Admin Panel | admin home | tabs | manage | /users,/geofences | system state | — | Admin only |
| User Management | CRUD users | table+form | create/edit/deactivate | /users | users | duplicate email | Admin only |
| Settings | profile | form | change password | /users/{me} | profile | password rules | self only |

**Navigation:** `Login → (role-based) Dashboard → {Repository, Upload, Verify, Audit(if permitted), Admin(if admin)}`. Sidebar items hidden by permission. Every sensitive action re-checks location.

---

## PART 17 — Database + API + Cloud Data Flow

```
UPLOAD:    React → POST /documents → JWT → RBAC → Geofence → file validate → R2 put(encrypted) → SHA-256 → Mongo(documents+versions) → 201
VIEW:      React → GET /documents/{id} → JWT → RBAC → Mongo read → 200 (metadata)
DOWNLOAD:  React → GET /{id}/download → JWT → RBAC → Geofence → Mongo read key → R2 pre-signed URL(60s) → client fetches from R2 → audit
VERIFY:    React → POST /verify/{v} → JWT → RBAC → R2 get bytes → SHA-256 → read stored hash(Mongo) → read on-chain(Sepolia) → 3-way compare → verification_records → 200
APPROVE:   React → POST /{id}/approve → JWT → RBAC → Geofence → Mongo status=APPROVED → enqueue anchor → BlockchainService sign+send(Sepolia) → tx hash → blockchain_anchors(PENDING) → worker confirms → CONFIRMED + ACTIVE
AMEND:     React → POST /{id}/amend → JWT → RBAC → Geofence → new version(DRAFT, prev_hash) → (then upload+review+approve cycle)
ARCHIVE:   React → POST /{id}/archive → JWT → RBAC → Mongo status=ARCHIVED → audit
```

---

## PART 18 — Smart Contract + Backend Integration

```
React → FastAPI(/approve) → BlockchainService → web3.py sign(SERVICE_WALLET_KEY) → Sepolia RPC(Alchemy) → DocumentAnchor.anchor()
      → tx hash → blockchain_anchors(PENDING) → worker polls → CONFIRMED → MongoDB update → UI shows Etherscan link
```

**Who signs — backend or MetaMask?** For a college prototype, **the backend signs** with a single service wallet. Reasons: (1) users don't need wallets or testnet ETH; (2) anchoring is an automatic system event, not a user action, so it belongs server-side; (3) simpler demos. **Trade-off (state it):** this is *custodial* — the backend is trusted to anchor honestly; it's not "user-owned" decentralization. The MetaMask alternative (each user signs) is more decentralized but impractical here (wallet onboarding, gas per user, UX friction). 

**Key safety rules:** private key only in backend secret store / env var (never frontend, never git, never logs); use a dedicated wallet holding only faucet ETH; add GitHub secret scanning + pre-commit hooks; rotate if exposed; the app always cross-checks recomputed vs stored vs on-chain so a single compromised anchor can't silently pass verification of a genuine doc.

---

## PART 19 — DevOps

**Repo structure (monorepo):**
```
geolegalvault/
├── frontend/            # React + Vite + TS
│   ├── src/{pages,components,api,hooks,lib}/ 
│   └── package.json
├── backend/             # FastAPI modular monolith
│   ├── app/
│   │   ├── main.py
│   │   ├── core/        # config, security, deps
│   │   ├── modules/{auth,users,documents,versions,geofences,audit,blockchain,verify}/
│   │   ├── services/    # hashing, storage(R2), blockchain, geofence
│   │   ├── models/      # pydantic + mongo schemas
│   │   └── workers/     # anchor confirmation poller
│   ├── tests/
│   ├── requirements.txt / pyproject.toml
│   └── Dockerfile
├── contracts/           # Hardhat
│   ├── contracts/DocumentAnchor.sol
│   ├── scripts/deploy.ts
│   ├── test/
│   └── hardhat.config.ts
├── docs/                # SRS, architecture, threat model, API, DB, test plan, deploy, user/dev guides, research
├── scripts/             # seed data, backup, faucet helper
├── .github/workflows/   # ci.yml
├── docker-compose.yml   # mongo + minio + backend + hardhat-node for dev
├── .env.example
├── .gitignore
└── README.md
```
**Branching:** trunk-based-lite — `main`(protected) + short-lived `feature/*` → PR → review → CI green → merge. Tag releases. **Env management:** `.env` per environment (dev/test/prod), `.env.example` committed, real values in platform secrets. **Docker:** compose spins Mongo + MinIO + Hardhat node + backend for one-command dev. **CI/CD (GitHub Actions):** on PR → lint (ruff/eslint) + type-check + backend pytest + frontend Vitest + Hardhat tests + build. On merge to main → deploy frontend (Vercel) + backend (Render) via hooks. **Rollback:** redeploy previous git tag / previous platform deploy; contract is immutable (deploy a new address if needed and update config). 

---

## PART 20 — Testing Strategy

| Layer | Tool | Sample cases |
|---|---|---|
| Unit | pytest / Vitest | hash correctness; geofence point-in-polygon true/false; RBAC map; state-machine transitions |
| Integration | pytest + httpx + test Mongo | upload→store→hash→metadata; approve→anchor(mock chain) |
| API | httpx / Postman | each endpoint × each role (authz matrix) |
| Frontend | React Testing Library | login form, upload validation, verify result render |
| Database | pytest | 2dsphere query returns correct fence; unique version index |
| Blockchain | Hardhat | anchor stores hash; re-anchor same (doc,version) reverts; onlyWriter enforced; getAnchor returns value |
| Security | manual + zap(opt) | expired JWT→401, alg=none→reject, IDOR→403, NoSQL injection payload→rejected, malicious filename→sanitized |
| Geospatial | pytest | inside/outside/edge point; low-accuracy→422; stale timestamp→422 |
| E2E | Playwright(opt) | full happy path + tamper-detect path |
| Performance | locust/k6(light) | upload latency, verify latency under a few concurrent users |

**Concrete cases:** valid login ✅ / invalid ✅→401 / unauthorized role→403 / outside geofence→403 / valid upload→201 / invalid file→422 / hash mismatch→MISMATCH / hash match→VERIFIED / blockchain tx failure→retry+pending / legitimate amendment→V2 created, V1 retained / unauthorized modification→detected on verify / expired JWT→401 / malicious filename→stored as UUID / duplicate document→allowed as new version or flagged by identical hash / missing GPS permission→blocked with message.

---

## PART 21 — Test Data / Document Dataset (legal & synthetic)

**Do not use real confidential documents.** Generate synthetic ones:
- **Types:** NDAs, service agreements, policy memos, MoUs, notices — from public templates or LLM-generated placeholder text with fake parties ("Acme Corp", "Officer A. Rao").
- **Volume:** ~30–50 documents, each with 2–3 versions (≈100 version blobs) — enough to demo search, lineage, verification, and archival without straining free tiers.
- **Controlled tampering cases:** keep 5 documents where you deliberately alter one byte in the stored blob *after* anchoring, to demo MISMATCH.
- **Legitimate amendments:** 5 documents that go V1→V2 through the proper workflow (both versions verify ✅).
- **Metadata variations:** mix doc_types, classifications, owners, tags, date ranges to exercise filters and reports.
- **Seed script** in `scripts/seed.py`: creates users (one per role), geofences (HQ polygon + a "denied" location), documents, versions, and a couple pre-anchored records.

---

## PART 22 — Performance Engineering

| Metric | Target (prototype) | How to measure |
|---|---|---|
| API response (non-chain) p95 | < 500 ms | middleware timing / k6 |
| Upload latency (≤10 MB) | < 5 s | client timer + server logs |
| Hashing (10 MB) | < 300 ms | time SHA-256 in service |
| Storage put | < 3 s | storage SDK timing |
| MongoDB query | < 50 ms (indexed) | Atlas profiler / explain() |
| Geofence query | < 50 ms | explain() with 2dsphere |
| Blockchain tx latency | 15 s–2 min (async, not blocking UX) | tx timestamp → confirmation |
| Verify (fetch+hash+read chain) | < 3 s | end-to-end timer |

**What matters:** user-facing latencies (upload, verify, queries) matter; blockchain latency is intentionally async so it never blocks the UI. Collect via FastAPI middleware (log duration per request), Mongo `explain()`, and a light k6/locust run at ~5–10 concurrent users. Don't overclaim throughput — this is a prototype.

---

## PART 23 — Cost Analysis

| Item | Tier | Cost | Notes |
|---|---|---|---|
| MongoDB Atlas M0 | Free forever | ₹0 | 512 MB — plenty for metadata |
| Cloudflare R2 | Free tier | ₹0 | 10 GB storage, **no egress fees** (key advantage) |
| Sepolia testnet + faucet ETH | Testnet | ₹0 | RPC via Alchemy/Infura free plan |
| Vercel/Netlify (frontend) | Free | ₹0 | HTTPS included |
| Render/Railway/Fly (backend) | Free tier | ₹0 | cold starts / limited hours |
| GitHub + Actions | Free | ₹0 | generous CI minutes |
| Sentry | Free | ₹0 | error tracking |
| **Total** | — | **₹0** | achievable |

**A. ₹0 dev plan:** everything above, single instance, small files. **B. Free-tier cloud plan:** same, hosted. **C. Minimal-cost deployment:** if you outgrow free (unlikely for a demo) — a $5–7/mo VPS or paid Render. **D. Unexpected costs:** AWS S3 egress/requests if you use S3 instead of R2 (→ use R2 or set billing alerts + budget cap); domain name (optional ~₹800/yr); exceeding Atlas/R2 quotas (→ cleanup jobs, size caps). **Cost-control rules:** testnet only, R2 not S3, hard file-size cap, one instance, delete test blobs, billing alerts on any card-linked account, never fund a real wallet.

---

## PART 24 — Project Management (2–4 students)

**MVP-first principle: get the happy path (login → geofenced upload → hash → approve → anchor → verify) working end-to-end before polishing anything.**

### 8-week (aggressive MVP)
| Wk | Focus | Deliverable | DoD | Risk |
|---|---|---|---|---|
| 1 | Setup, repo, auth skeleton, Mongo | running FastAPI + login | login works, CI green | env setup delays |
| 2 | RBAC + users + geofence CRUD + 2dsphere | geofence check works | inside/outside returns correct | GeoJSON lng/lat bug |
| 3 | Upload + R2 + validation + SHA-256 + versions | upload→store→hash→metadata | file stored, hash saved | storage keys/CORS |
| 4 | Smart contract + deploy Sepolia + anchor service | anchor on approve | tx on Etherscan | faucet/RPC limits |
| 5 | Verify pipeline + review/approval workflow | 3-way verify | VERIFIED + MISMATCH demo | chain read edge cases |
| 6 | Frontend core pages + audit log | usable UI | happy path clickable | frontend time sink |
| 7 | Amendment/versioning + admin + hardening | V2 flow + tests | lineage retained | scope creep |
| 8 | Testing, demo prep, docs | demo + report | full demo runs twice | integration bugs |

### 10-week = 8-week + Weeks 9 (edge cases, security tests, reporting) & 10 (polish, performance, docs, dry-run demo).
### 12-week = 10-week + Weeks 11 (optional: ClamAV, email notifications, Playwright e2e) & 12 (research write-up, paper draft, buffer).

Owner/dependencies per week assigned in Part 25.

---

## PART 25 — Team Responsibility (balanced)

| Member | Primary | Secondary | Owns |
|---|---|---|---|
| M1 — Backend/API lead | FastAPI, auth, RBAC, workflow state machine | integration | endpoints, business logic, tests(API) |
| M2 — Blockchain/Cloud | Solidity+Hardhat, web3.py service, R2/S3 storage, secrets | backend | contract, anchoring, storage, deploy |
| M3 — Frontend/Geo | React UI, geolocation gate, geofence integration | UX, docs | pages, client validation, maps |
| M4 — DB/Security/QA/Research | Mongo schema+indexes, threat model, test plan, CI, paper | any | data design, security tests, documentation, research |

**2-person fallback:** M1 = backend+blockchain+cloud; M2 = frontend+db+geo+security+docs. Cut Level-3 features hard.

Coverage matrix (everyone touches ≥2 areas): Frontend(M3,M1), Backend(M1,M2), Blockchain(M2,M4), DB(M4,M1), Cloud(M2,M4), Security(M4,M1), Testing(M4,all), Docs(M4,M3), Research(M4,M2).

---

## PART 26 — MVP vs Advanced (be ruthless)

**LEVEL 1 — MUST HAVE (MVP, cannot ship without):** JWT auth; RBAC (≥3 roles); geofence CRUD + server-side point-in-polygon enforcement on sensitive ops; document upload → encrypted R2 storage; SHA-256 hashing; immutable versioning (V1/V2, prev-hash chain); review→approve workflow; blockchain anchoring on approval (service wallet, Sepolia); 3-way integrity verify with MISMATCH detection; audit logging; core frontend (login, repo, upload, details, verify, version history); tamper-detection demo.

**LEVEL 2 — SHOULD HAVE:** full 5-role matrix + Auditor; amendment workflow polish; admin/user management UI; audit-log UI with filters; reporting dashboard; background worker for confirmations; geofence map UI; performance measurements; solid test suite + CI.

**LEVEL 3 — NICE TO HAVE (only if ahead):** ClamAV scanning; email notifications; Playwright e2e; GPS-spoof heuristics; log-batch hashing; export/PDF reports; multiple geofence policies per role; re-anchoring on testnet reset.

**Ruthless rule:** if by end of Week 5 the anchor+verify path isn't solid, freeze all Level-2/3 and finish the loop. A tight MVP that demonstrably detects tampering beats a broad half-working app.

---
## PART 27 — Research / Novelty

**Is "blockchain for documents" novel? No — and don't claim it.** Hash-anchoring documents on-chain is a well-trodden pattern (notary/timestamping services, many student and commercial projects). RBAC document management is standard. Geofencing is standard in mobility apps.

**What is uncommon here (the honest contribution):** the *specific integration and enforcement pipeline* — **geospatial authorization gating document-lifecycle operations, combined with per-version on-chain anchoring and immutable version lineage, within one workflow.** The novelty is *integration + the three-gate enforcement model (identity → role → location) applied to a verifiable-integrity document lifecycle*, not any single primitive.

- **Existing common approaches:** on-chain hash notarization; blockchain DMS prototypes; geofenced access in mobile/IoT; RBAC DMS.
- **What we combine differently:** location policy as a *first-class gate on document operations* + per-version anchoring + verifiable lineage in a single system.
- **Real novelty:** modest but defensible — the *composed system and its enforcement semantics*, presented with an honest threat model.
- **Engineering contribution:** a working, reproducible, ₹0 reference implementation integrating cloud storage + NoSQL geospatial + EVM anchoring with clean separation of concerns.
- **Potential research contribution:** an evaluation of the pattern's usefulness/limits (esp. the honest analysis of why browser geofencing is insufficient and what would be needed) — this critical framing is itself publishable-adjacent as an experience/architecture paper, not as a breakthrough.
- **Claims to AVOID:** "military-grade," "tamper-proof" (say tamper-*evident*), "secure location guarantee," "novel blockchain technique," "prevents insider tampering" (you *detect* it).

**Keeping Project 1 distinct from TARP:** TARP = blockchain + hierarchical hashing/Merkle + provenance + NLP semantic tamper-*localization* (where inside a doc it changed). Project 1 = blockchain + cloud + NoSQL + geospatial authorization + whole-document lifecycle integrity (that a doc changed, and version lineage). Boundary line: **Project 1 detects that a document/version changed and enforces where operations happen; TARP localizes and semantically characterizes intra-document tampering.** No Merkle/NLP in Project 1.

---

## PART 28 — Patent / Prior-Art Considerations

**How to do a prior-art search (methodology):**
1. Define your claim in one sentence (the geofenced-lifecycle + per-version anchoring combination).
2. Search patent databases: **Google Patents**, **USPTO Patent Public Search**, **Espacenet (EPO)**, **WIPO PatentScope**, and India's **InPASS**. Use keyword combos: `blockchain document integrity`, `geofencing access control document`, `hash anchoring version provenance`, `location based document authorization`.
3. Search academic sources: **Google Scholar**, **IEEE Xplore**, **ACM DL**, **arXiv**, **Semantic Scholar**, **Scopus** — same keyword combinations plus `+ RBAC + NoSQL`.
4. Search products/repos: GitHub, product docs of DMS + notary tools.
5. Record each hit's category, closest claim, and how yours differs.

**Categories of likely prior art (I will not fabricate patent numbers):**
- Patents on **blockchain-based document/record integrity and timestamping** (large, crowded space).
- Patents/papers on **geofencing / location-based access control** (mobility, IoT, MDM).
- Patents on **secure cloud document management + RBAC**.
- Academic papers on **blockchain DMS**, **document provenance on blockchain**, **hash-anchoring notarization**.
- Products: on-chain notary services, enterprise DMS with audit trails.

**Patent vs prior art vs paper vs product vs your contribution:** a *patent* is a granted legal right over a claim; *prior art* is anything public before your filing that discloses the idea (kills novelty); a *research paper* is academic disclosure (also prior art); a *product* is a commercial implementation (also prior art); *your contribution* is the specific integration + honest evaluation, likely **not patentable** because the components exist and combination-only claims face obviousness rejections.

**Is patenting realistic for a college project? No, and don't aim for it.** Patents cost money, take years, and require demonstrable non-obvious novelty. Your realistic outputs are a strong report + possibly a workshop/conference paper. (I did not run live database searches in this document; run the searches above yourself and cite exact results — never invent patent numbers.)

---

## PART 29 — Academic Paper / Publication Strategy

- **Suitable for a paper? Conditionally** — as an *experience/architecture/evaluation* paper (student conference, workshop, or a systems course venue), **not** as a novel-algorithm paper. Don't call it publishable just because it uses blockchain.
- **Research question:** *"What are the practical benefits, costs, and security limits of combining geospatial authorization with per-version blockchain anchoring in a document-lifecycle system, and where does browser-based geofencing fail as a security control?"*
- **Methodology:** build the system; run controlled experiments (tamper vs no-tamper detection, geofence in/out, spoofing attempts); measure latencies and detection accuracy; qualitatively analyze the threat model.
- **Metrics:** integrity-detection accuracy (should be 100% for byte changes), verify latency, anchor latency/cost (gas), geofence decision correctness, spoofing-detection rate of heuristics (expected low — report honestly).
- **Experimental setup:** synthetic dataset (Part 21), N documents/versions, controlled tampering, several devices/locations (real + spoofed).
- **Baselines:** DB-only integrity (signed hash, no chain) vs chain-anchored; access control with vs without geofence.
- **Expected results:** cryptographic tamper-*evidence* works reliably; geofencing adds policy value but is bypassable by spoofing (this honest negative result is a real contribution).
- **Limitations:** browser GPS spoofability; testnet reliability; custodial signing; small scale.

---

## PART 30 — Deployment Plan

**Development (local):** docker-compose (Mongo + MinIO + Hardhat node + backend) + Vite dev server. **Demo:** frontend on Vercel, backend on Render, MongoDB Atlas M0, R2 bucket, contract on Sepolia. **Production-like:** same as demo + HTTPS everywhere, private bucket, IP-allow-listed Atlas, secrets in platform vault, Sentry monitoring, health checks, backups.

**Exact deployment sequence:**
1. Deploy `DocumentAnchor.sol` to Sepolia via Hardhat; record contract address; fund service wallet from faucet.
2. Provision Atlas M0 (user + IP allow-list) and R2 bucket (private + scoped key).
3. Set backend env (Mongo URI, R2 keys, RPC URL, service wallet key, JWT secret, contract address) in Render secrets.
4. Deploy backend container to Render; run seed script; verify `/health`.
5. Set frontend env (API base URL) and deploy to Vercel.
6. Smoke test full happy path + tamper-detect path.
7. Enable Sentry + confirm logs; take a DB snapshot.

---

## PART 31 — Backup / Disaster Recovery

| Failure | Plan |
|---|---|
| MongoDB data loss | Atlas snapshots + weekly `mongodump` to a second free store; restore procedure documented |
| Storage object loss | R2 object versioning ON; keep source docs in a separate backup bucket |
| Document recovery | version blobs immutable + versioned; restore from backup by storage_key |
| Blockchain anchor "loss" (testnet reset) | anchors also stored locally with tx hash + block; re-anchor capability if a fresh chain is needed; report notes testnet impermanence |
| Lost wallet/private key | rotate to a new service wallet, re-anchor future events; past on-chain records remain readable; **never** store real value in it |
| DB corruption | restore latest good snapshot; verify with on-chain hashes (corruption is detectable) |
| Cloud outage | app tolerates async; retry storage/RPC; static frontend stays up; document RTO/RPO expectations (best-effort for a prototype) |
| Blockchain outage/RPC down | anchoring queued + retried; verification degrades gracefully (compare stored hash, mark on-chain "unavailable, retry") |

---

## PART 32 — Observability

- **Application logs:** structured JSON (request id, route, duration, status) via FastAPI middleware.
- **Security logs:** auth successes/failures, authz denials, geofence denials, rate-limit hits.
- **Audit logs:** append-only in `audit_logs` (actor, action, target, result, location, ts) — user-facing to Auditor/Admin.
- **Blockchain tx logs:** tx hash, status, block, gas, retries in `blockchain_anchors` + logs.
- **Error monitoring:** Sentry captures exceptions with context.
- **Metrics:** request latency, error rate, anchor success rate, verify pass/fail counts.
- **Health checks:** `/health` returns app + Mongo + storage + RPC reachability.

Examples: `{"lvl":"WARN","event":"GEOFENCE_DENIED","actor":"u_07","point":[78.9,11.1],"ts":"..."}`; `{"event":"ANCHOR_OK","version":"v_2","tx":"0xabc","block":5123456}`.

---

## PART 33 — Documentation

| Doc | Structure (sections) |
|---|---|
| SRS | intro, scope, actors, functional reqs, non-functional reqs, constraints, acceptance |
| Architecture doc | logical/physical/data-flow/security/blockchain diagrams + decisions + trade-offs |
| API doc | auto OpenAPI/Swagger + auth guide + error catalogue |
| DB design | collections, fields, indexes, geospatial queries, rationale |
| Threat model | assets, threats (Part 14 table), mitigations, residual risk, honest limits |
| Test plan | strategy, cases, coverage, results |
| Deployment guide | env setup, deploy sequence (Part 30), rollback |
| User manual | per-role how-to with screenshots |
| Developer guide | local setup, repo structure, contributing, conventions |
| Research methodology | RQ, method, metrics, baselines, results, limitations |
| Final report | everything, academic format |
| PPT | problem → solution → architecture (horizontal diagrams) → demo → novelty → limits |
| Demo script | Part 34 |

---

## PART 34 — Demo Plan (10 minutes)

| Min | Step | On screen |
|---|---|---|
| 0:00 | Login as Legal Officer | login → dashboard, **role badge** visible |
| 0:45 | Location authorization | Geofence Status page: green "Inside HQ", coordinates + accuracy |
| 1:30 | Upload contract (in geofence) | upload progress → 201, doc in repo, **SHA-256 shown** |
| 2:30 | Show cloud storage | R2 console: encrypted object with UUID key (private) |
| 3:15 | Show MongoDB metadata | Atlas: `documents` + `document_versions` doc with hash |
| 4:00 | Submit → review → **approve** | status transitions; approve triggers anchoring |
| 5:00 | Blockchain anchor | `blockchain_anchors` PENDING→CONFIRMED, **Etherscan tx link** opened |
| 6:00 | Amend → **create V2** | upload corrected file; version history shows V1(SUPERSEDED)+V2(ACTIVE), both anchored |
| 7:00 | **Attempt unauthorized modification** | overwrite V2 blob in R2 directly (show the console action) |
| 7:45 | Verify V2 | click Verify → **red INTEGRITY FAILED**, 3-way hash mismatch |
| 8:30 | Verify V1 | **green VERIFIED** (unchanged version still passes) |
| 9:00 | Audit trail | audit log shows every action incl. VERIFY_FAIL + geofence events |
| 9:30 | Attempt from outside geofence (spoof toggle) | 403 GEOFENCE_DENIED message |
| 10:00 | Close: one slide of honest limitations | "tamper-evident, not tamper-proof; geofence is policy, not guarantee" |

---

## PART 35 — Edge Cases (30+)

| # | Case | Expected behavior |
|---|---|---|
| 1 | User outside geofence | 403 GEOFENCE_DENIED, audited, no storage access |
| 2 | GPS unavailable/permission denied | sensitive ops blocked with clear message; read-only allowed if policy permits |
| 3 | GPS accuracy poor (>100 m) | 422 LOW_CONFIDENCE, fail-closed |
| 4 | Stale location timestamp | 422 STALE, re-request location |
| 5 | Duplicate upload (same bytes) | allowed as new version OR flagged "identical hash exists" (config) |
| 6 | Same file uploaded twice as new doc | permitted; identical hash noted, separate docId |
| 7 | Modified file after anchoring | verify → MISMATCH, doc flagged TAMPERED, alert |
| 8 | Blockchain RPC unavailable | anchor queued + retried; app usable; verify marks on-chain "unavailable" |
| 9 | Tx pending long | status PENDING; worker keeps polling; UI shows pending |
| 10 | Tx rejected/reverted | FAILED → retry ×k → alert; doc stays APPROVED(pending) |
| 11 | Out of testnet ETH | anchor fails → alert to refund from faucet |
| 12 | Storage (R2) unavailable | upload 503 with rollback (no orphan metadata); download retried |
| 13 | MongoDB unavailable | 503; health check red; no partial writes |
| 14 | Expired JWT | 401 → client refresh flow |
| 15 | Reused refresh token (replay) | revoke session family, force re-login |
| 16 | Unauthorized role for action | 403, audited |
| 17 | File too large | 413/422 before storage, size cap enforced |
| 18 | Unsupported format | 422 (MIME+magic mismatch) |
| 19 | Corrupted PDF | validation fails → 422 |
| 20 | Malicious filename (path traversal) | ignored; server generates UUID key |
| 21 | Executable disguised as PDF | magic-byte check rejects |
| 22 | User deleted while owning documents | soft-deactivate only; docs retain owner ref; reassign or keep historical |
| 23 | Geofence deleted while assigned | assignment invalidated; ops fail-closed until reassigned; existing docs unaffected |
| 24 | Network interruption during upload | incomplete → no metadata commit; client retries (idempotency key) |
| 25 | Concurrent amendment on same doc | version_no unique index prevents duplicate Vn; second writer gets conflict → retry |
| 26 | Approver == uploader (maker-checker) | rejected by validation |
| 27 | Verify a never-anchored version | result NOT_ANCHORED (not an error) |
| 28 | Spoofed GPS inside fence | accepted (limitation) but IP mismatch/velocity flagged + logged |
| 29 | Audit query by non-auditor | 403 |
| 30 | Contract address wrong/misconfigured | anchor fails fast; health check flags; config validated at boot |
| 31 | Very large geofence polygon | vertex cap on create; reject malformed ring |
| 32 | GeoJSON lat/lng swapped | input validation catches implausible coords |
| 33 | Testnet reset wipes anchors | local records + tx hashes retained; re-anchor path documented |

---
## PART 36 — Final Technical Blueprint (consolidated)

1. **Architecture:** React SPA → FastAPI modular monolith (Auth/RBAC/Geofence/Doc/Hash/Version/Audit/Blockchain modules) → MongoDB Atlas (metadata+geo+audit) + Cloudflare R2 (encrypted blobs) + Sepolia (DocumentAnchor contract) + optional confirmation worker.
2. **Tech stack:** React+Vite+TS+Tailwind · FastAPI+Python · JWT+Argon2id · MongoDB(2dsphere) · Cloudflare R2 · Solidity+Hardhat+web3.py · Sepolia · Docker+compose · GitHub Actions · Sentry · Vercel+Render.
3. **DB schema:** users, documents, document_versions(immutable), geofences(2dsphere), permissions(opt), audit_logs(append-only), blockchain_anchors, verification_records.
4. **API:** /auth, /users, /geofences, /documents(+submit/review/approve/amend/archive/download/versions), /verify, /blockchain, /audit, /health.
5. **Smart contract:** `DocumentAnchor` with `anchor(documentId,version,hash,eventType)` (onlyWriter, no re-anchor), `getAnchor(...)`, `AnchorCreated` event.
6. **Security model:** TLS → JWT → deny-by-default RBAC → server-side geofence → input/file validation → least-priv storage keys → encryption at rest → append-only audit → on-chain tamper-evidence.
7. **Cloud design:** private R2 bucket + pre-signed URLs; Atlas M0 IP-allow-listed; secrets in platform vault; Sentry + logs; snapshots + R2 versioning.
8. **Folder structure:** monorepo (Part 19).
9. **Roadmap:** MVP loop by Week 5, harden+UI by Week 7, test+demo+docs by Week 8; extend to 10/12 weeks for Level-2/3 + research.
10. **MVP definition:** login → geofenced upload → hash → approve → anchor(Sepolia) → 3-way verify with tamper detection → audit + version lineage.

---

## PART 37 — Hard Reality Check (brutally honest)

1. **Can 2–4 students build this?** Yes — the MVP is realistic. The risk isn't difficulty of any one piece; it's *integration surface* (auth+geo+storage+chain wired together).
2. **8–12 weeks?** MVP in 8 (tight), comfortable in 10–12. Don't attempt Level-3 in 8 weeks.
3. **₹0?** Yes, using R2 + Atlas M0 + Sepolia + Vercel + Render. The only ₹ risk is choosing S3 carelessly or buying a domain.
4. **Highest-risk components:** (a) blockchain integration (faucets, RPC limits, nonce/confirmation handling); (b) geofence correctness (lng/lat order, accuracy handling); (c) storage wiring (pre-signed URLs, CORS, keys); (d) integration timing across the team.
5. **If you fall behind, cut in this order:** email notifications → ClamAV → reporting dashboard → spoof heuristics → admin UI polish → Auditor role → background worker (do anchoring synchronously with a spinner). **Never cut:** upload→hash→anchor→verify→tamper-detect, or the geofence check.
6. **What impresses interviewers:** clean separation of concerns; correct off-chain/on-chain split; a *working* tamper-detection demo; server-side geofence with honest threat model; least-privilege cloud + secrets discipline; CI + tests.
7. **What a professor will criticize:** any "military-grade"/"tamper-proof" wording; browser-GPS-as-security; custodial signing described as "decentralized"; overstated novelty. Pre-empt all of these by stating limits first.
8. **Security claims to avoid:** "military-grade," "tamper-proof," "unhackable," "guaranteed location," "prevents insider modification." Use "tamper-evident," "detects modification," "policy-level geofencing," "prototype."
9. **What makes it more than CRUD:** the *verification loop* (recompute → compare stored → compare on-chain) that detects out-of-band tampering a normal DB can't, plus geofenced authorization and immutable anchored lineage. A CRUD app trusts its DB; this one can prove its DB wasn't silently altered.
10. **Single strongest feature:** **out-of-band tamper detection via on-chain hash comparison** — the live red/green verify against Etherscan.
11. **Weakest part:** **browser-based geofencing** (spoofable). Turn the weakness into a strength by analyzing it honestly.
12. **What I'd change before you start:** (a) drop "military," (b) commit to backend service-wallet signing, (c) pick R2 over S3, (d) exclude Merkle/NLP, (e) write the tamper-detection demo script *first* and build backward from it.

---

## FINAL DELIVERABLES

### A. LOCKED ARCHITECTURE
React SPA (Vercel) → FastAPI modular monolith (Render) with modules {Auth, RBAC, Geofence, Document, Hashing, Version, Audit, Blockchain} → **MongoDB Atlas M0** (metadata, geofences w/ 2dsphere, audit, anchors, verifications) + **Cloudflare R2** (encrypted document blobs, pre-signed URLs) + **Ethereum Sepolia** (`DocumentAnchor` contract, backend service-wallet signing) + optional confirmation worker. Enforcement pipeline on every sensitive op: **TLS → JWT → RBAC(deny-by-default) → server-side geofence → validation → action → audit.** Integrity = SHA-256 recompute vs stored vs on-chain.

### B. LOCKED TECH STACK
Frontend: React + Vite + TypeScript + Tailwind + TanStack Query. Backend: Python + FastAPI + Pydantic. Auth: JWT (PyJWT) + Argon2id. DB: MongoDB Atlas (2dsphere). Storage: Cloudflare R2 (S3-compatible). Blockchain: Solidity + Hardhat + web3.py + Ethereum Sepolia (Alchemy RPC). DevOps: Docker + docker-compose + GitHub Actions. Observability: Sentry + structured logs. Hosting: Vercel (FE) + Render (BE). Cost: **₹0**.

### C. MUST BUILD
JWT auth; RBAC (≥3 roles); geofence CRUD + server-side point-in-polygon enforcement; encrypted upload to R2; SHA-256 hashing; immutable versioning with prev-hash chain; review→approve workflow; blockchain anchoring on approval; 3-way integrity verification with MISMATCH detection; audit logging; core frontend (login, repo, upload, details, version history, verify); tamper-detection demo.

### D. OPTIONAL (only if ahead)
Full 5-role matrix + Auditor; amendment UI polish; admin/user management UI; audit-log filters; reporting dashboard; background confirmation worker; geofence map; performance measurement suite; ClamAV; email notifications; Playwright e2e; spoof heuristics.

### E. DO NOT BUILD
On-chain document storage; Merkle/hierarchical hashing/NLP (→ TARP); per-user MetaMask signing; microservices/message brokers; mainnet deployment; real GPS hardware attestation; multi-tenant billing; anything justifying a "military-grade" claim; over-engineered smart-contract upgradeability.

### F. FIRST 7 DAYS (exact tasks)
1. **Day 1:** Create monorepo (Part 19 structure), `.gitignore` + `.env.example`, docker-compose (Mongo+MinIO+Hardhat), README. Everyone gets it running locally.
2. **Day 2:** FastAPI skeleton + health check + MongoDB connection + `users` collection + Argon2id hashing.
3. **Day 3:** JWT login/refresh/logout + auth middleware + one protected route. Frontend login page hitting it.
4. **Day 4:** RBAC dependency + role map + `geofences` collection with **2dsphere** index + geofence CRUD.
5. **Day 5:** Server-side geofence check endpoint (point-in-polygon), unit-tested with inside/outside/edge points. Fix lng/lat order now.
6. **Day 6:** R2 bucket + storage service (put + pre-signed get) + file validation + SHA-256 service; upload endpoint creating `documents`+`document_versions`.
7. **Day 7:** Deploy `DocumentAnchor.sol` to Sepolia, fund service wallet, `anchor()`/`getAnchor()` via web3.py from a script. **Write the demo script (Part 34) now** and build the rest backward from it.

### G. DEFINITION OF DONE (objective, provable)
- [ ] A user can register (by admin), log in, and receive a valid JWT.
- [ ] Sensitive operations are blocked outside an authorized geofence (server-side) and allowed inside — demonstrated with two locations.
- [ ] A document can be uploaded, encrypted at rest in R2, hashed (SHA-256), and its metadata + version stored in MongoDB.
- [ ] Approval anchors the version's hash on Sepolia; the tx is viewable on Etherscan and stored in `blockchain_anchors`.
- [ ] An amendment creates V2 without destroying V1; both versions independently verify.
- [ ] Clicking Verify recomputes the hash and compares it to stored + on-chain: **VERIFIED** for an untouched file, **MISMATCH** for a tampered one (demonstrated live).
- [ ] Every security-relevant action appears in an append-only audit log visible to Auditor/Admin.
- [ ] RBAC is enforced for every endpoint (tested per role); deny-by-default holds.
- [ ] The full 10-minute demo runs end-to-end twice without manual DB fixes.
- [ ] Core services have automated tests; CI is green on main.
- [ ] Documentation set (SRS, architecture, threat model with **honest limitations**, API, DB, test plan, deploy guide, user/dev guides, report, PPT, demo script) is complete.
- [ ] No secrets in git; all keys in env/secret store; no "military-grade"/"tamper-proof" claims anywhere.

---

*End of plan. This is a delivery blueprint, not a description — build the tamper-detection loop first, keep the honesty about geofencing front and center, and the project will read as real engineering.*
