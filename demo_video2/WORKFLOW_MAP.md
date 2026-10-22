# GeoLegalVault – Workflow Map (UI action → endpoint → service → collection → storage → contract)

Built by reading the code on 2026-10-21 (Phase 1, read-only). Paths are relative to the repo root.
Everything here was read from source, not assumed. Where it is a limit, it says so.

## 1. Enforcement order on a sensitive request (Guardrail #5)
TLS → JWT (`core/deps.py`) → RBAC (`core/rbac.py::require`) → geofence (`services/geofence.py::require_geofence`)
→ input/file validation → action → audit (`modules/audit/service.py::record`).
The body-size cap (`core/body_limit.py`) runs first, before the body is read.

## 2. Roles (`core/rbac.py::ROLE_PERMISSIONS`) and default clearance (`core/clearance.py`)
| Role | Clearance (seed) | Can |
|---|---|---|
| ADMINISTRATOR | INTERNAL | users, geofences, audit, view, verify, archive, clear integrity flag, view/re-queue stuck anchors. **Cannot upload, review or approve.** |
| AUTHORIZED_STAFF | CONFIDENTIAL | upload, submit, amend, view, verify |
| REVIEWING_OFFICER | RESTRICTED | review (approve review / request changes), view, verify |
| LEGAL_OFFICER | RESTRICTED | upload, submit, amend, archive, **approve**, view, verify, view anchors |
| AUDITOR | RESTRICTED | audit log, view, verify, view anchors |

Clearance order: PUBLIC < INTERNAL < CONFIDENTIAL < RESTRICTED < TOP_SECRET. A document above the caller's clearance
is a **404** (same body as a non-existent id), never 403 (`modules/documents/access.py`). New users start at PUBLIC.
`doc_type` is free text with no behaviour attached (the Upload form only shows the placeholder "e.g. CONTRACT").

## 3. Lifecycle (`modules/documents/workflow.py`)
```
Upload ─► DRAFT ─submit(uploader only)─► SUBMITTED ─review(reviewer ≠ uploader)─► UNDER_REVIEW ─► PENDING_APPROVAL
   (changes requested: ─► CHANGES_REQUESTED ─► DRAFT)
PENDING_APPROVAL ─approve(approver ≠ uploader, geofenced)─► APPROVED ─anchor tx confirmed─► BLOCKCHAIN_ANCHORED ─► ACTIVE
ACTIVE ─request amendment (geofenced)─► AMENDMENT_REQUESTED ─upload V(n+1)─► DRAFT … (V(n) becomes SUPERSEDED on V(n+1) ACTIVE)
ACTIVE ─archive─► ARCHIVED
```
A normal happy path therefore needs **three people**: uploader (Staff) → Reviewing Officer → Legal Officer.
`UNDER_REVIEW` is passed through inside one `review` call, so the UI normally shows SUBMITTED → PENDING_APPROVAL.
If the anchor cannot be sent or is slow, the document stays **APPROVED** (not ACTIVE) and the anchor worker (opt-in) retries.

## 4. UI → backend map
All endpoints are under `/api/v1`. "G" = geofenced (needs `lat,lng,accuracy,timestamp` as `X-Geo-*` headers or form/JSON fields).

| # | UI route / button | Endpoint | Auth/RBAC | G | Service code | Mongo (write) | Storage | Contract | Audit action |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `/login` Sign in | `POST /auth/login` | none; 5 failures per email = lockout (`auth/service.py`) | – | `auth/service.py` | `users.last_login`, `refresh_sessions`, `login_rate_limits` | – | – | LOGIN_SUCCESS / LOGIN_FAILURE |
| 2 | `/geofence-status` | (browser only) `navigator.geolocation` via `hooks/useGeoLocation.ts` | – | – | none: the server decides on each G call | – | – | – | – |
| 3 | `/admin` → Users | `POST/GET/PATCH /users` | `users:manage` | – | `users/service.py` | `users` | – | – | USER_CREATE / USER_UPDATE |
| 4 | `/admin` → Geofences | `POST/GET/PATCH /geofences` | `geofence:manage` | – | `geofences/service.py` (+`bbox.py`) | `geofences` (GeoJSON Polygon, `[lng,lat]`, 2dsphere) | – | – | GEOFENCE_CREATE / UPDATE |
| 5 | `/documents/upload` Upload | `POST /documents` (multipart) | `document:upload` | **G** | `documents/service.py::create_document_with_v1`, `services/hashing.py::sha256_bytes` | `documents` (DRAFT), `document_versions` (V1, `sha256`, `storage_key`) | `put_object` key `docs/<documentId>/v<n>-<sha256>` | – | UPLOAD |
| 6 | Document Details → Submit for review | `POST /documents/{id}/submit` | `document:submit`, must be V's uploader | – | `workflow.submit` | `documents.status`, `document_versions.status` | – | – | SUBMIT |
| 7 | Document Details → Review → Approve review / Request changes | `POST /documents/{id}/review` | `review:perform`, reviewer ≠ uploader (`MAKER_CHECKER_VIOLATION`) | – | `workflow.review` | status fields, `review_feedback` | – | – | REVIEW_START, REVIEW_PASS or CHANGES_REQ |
| 8 | Document Details → Approve | `POST /documents/{id}/approve` | `approve:perform`, approver ≠ uploader | **G** | `workflow.approve` → `blockchain/service.py::anchor_document_version` → `services/blockchain.py` (web3.py, service wallet) | `documents`/`document_versions` status, `blockchain_anchors` (PENDING → CONFIRMED, `tx_hash`, `block_number`), `document_versions.anchored/anchor_id` | – | `DocumentAnchor.anchor(documentId, version, hash, eventType=1)` | APPROVE, ANCHOR_OK / ANCHOR_FAIL, ACTIVATE |
| 9 | Version History → View on-chain (`/versions/:id/blockchain`) | `GET /blockchain/anchor/{versionId}` | `anchor:view` (or document view) | – | `blockchain/router.py::get_anchor` live read | – | – | `getAnchor(documentId, version)` (view call, no gas) | – |
| 10 | Document Details → Download | `GET /documents/{id}/download` | `document:view` | **G** | `documents/router.py` → `storage.generate_presigned_get` | – | pre-signed GET, TTL 60 s (default) | – | ACCESS |
| 11 | Document Details → Request amendment (`/documents/:id/amend`) | `POST /documents/{id}/amend` | `document:amend` | **G** | `workflow.request_amendment` | status | – | – | AMEND_REQ |
| 12 | Upload amended version | `POST /documents` with `amend_of` | `document:amend` | **G** | `documents/service.py::create_next_version` | new `document_versions` row, `prev_version_hash` = V(n) hash | new object | – | UPLOAD |
| 13 | Version History → Verify (`/verify/:versionId`) → Run verification | `POST /verify/{versionId}` | `verify:perform` + clearance | – | `verify/service.py::verify_version` | `verification_records` (append-only); on MISMATCH `documents.integrity_flag=TAMPERED` | `get_object(storage_key)` | `getAnchor(...)` view call | VERIFY_PASS / VERIFY_FAIL / VERIFY_NOT_ANCHORED / … |
| 14 | `/audit` | `GET /audit` | `audit:view`; `meta` blanked above clearance | – | `audit/service.py` | – | – | – | – |
| 15 | Dashboard banner | `GET /blockchain/anchors/attention`; retry `POST /blockchain/anchors/{id}/retry` | `anchor:view` / `anchor:retry` (admin) | retry = **G** | `blockchain/retry.py` | `documents.anchor_retry` | – | never contacts chain | ANCHOR_RETRY_REQUESTED |
| 16 | Admin Panel → Health / Reports | `GET /health`, `GET /reports/summary` | – / admin | – | `core/health.py`, `reports/service.py` | – | – | – | – |

## 5. Geofence rules (`services/geofence.py::check_location`) – order of checks
1. Accuracy > `GEO_ACCURACY_MAX_M` → **422 `LOCATION_LOW_CONFIDENCE`** (fail-closed). *This machine's `.env` sets 300; code default is 100.*
2. Reading older than `GEO_FRESHNESS_MAX_SEC` → **422 `LOCATION_STALE`**. *`.env` sets 120; code default is 60.*
3. Point-in-polygon: Mongo `$geoIntersects` against **only the fences listed in the user's `assigned_geofence_ids`** that are `active` → otherwise **403 `GEOFENCE_DENIED`** and an audit row `GEOFENCE_DENIED`.
4. Missing/invalid fields → **422 `INVALID_LOCATION`**.
The server never reads an "allowed" flag from the client.

## 6. What is written on-chain (`contracts/contracts/DocumentAnchor.sol`)
`anchor(string documentId, uint32 version, bytes32 hash, uint8 eventType)`; only addresses in `writers` may call it (`onlyWriter`).
Stored: `{hash, version, eventType, ts(block.timestamp), exists}` under key `keccak256(documentId, version)`; emits `AnchorCreated`.
A second anchor for the same (documentId, version) reverts with `already anchored`. `getAnchor(documentId, version)` → `(hash, eventType, ts, exists)`.
No file bytes, filename or user data. Not upgradeable. One SHA-256 per file; **no Merkle tree**. Single backend service wallet signs.

## 7. Verification (`verify/service.py`) – real order
1. Load version row (clearance check → 404 if hidden). 2. Read the stored object from storage (`FILE_MISSING` if absent).
3. Recompute SHA-256 of those bytes. 4. Compare with `document_versions.sha256` ("stored"). 5. Read `getAnchor` live ("on-chain").
Verdict table:
| Verdict | When |
|---|---|
| VERIFIED | on-chain hash exists AND recomputed == stored AND recomputed == on-chain |
| MISMATCH | on-chain hash exists but recomputed differs from stored or on-chain (also when chain is unreachable but DB claims anchored and recomputed ≠ stored); sets `integrity_flag=TAMPERED` |
| NOT_ANCHORED | chain has no record and the DB does not claim an anchor (e.g. a DRAFT) |
| ANCHOR_MISSING | DB claims anchored, chain says no anchor/contract, file hash is fine; flags UNCONFIRMED |
| CHAIN_UNREACHABLE | chain could not be read; no verdict |
| FILE_MISSING | storage says no such object; flags UNCONFIRMED |

**Important:** verification re-reads the file already in storage. The app has **no "upload a file to compare" feature** (nothing in the code
produces verdicts like `AUTHENTIC_LATEST` that appear in `demo/last_run.json` and the `demo/tampered_*.pdf` files; those belong to something
other than this codebase and are not used). `demo/tamper.py` therefore tampers the **stored object in place** (+1 to byte 0 of the latest version).

## 8. MongoDB (db `geolegalvault`; the demo recording used `geolegalvault_demo`) – see `MONGODB_COLLECTIONS.md`. Storage: bucket `geolegalvault-dev`, key `docs/<documentId>/v<n>-<sha256>`.

## 9. Demo tooling
- `scripts/seed.py --demo`: 5 demo users (password in `DEMO_RUNBOOK.md`, not repeated here), fence "HQ Campus (demo)" polygon lng 78.14–78.16, lat 11.66–11.68; inside point lat 11.67 lng 78.15; outside lat 11.00 lng 77.00. Idempotent. (Do **not** use `--seed-documents`: it sends many real transactions.)
- `demo/tamper.py "<title>"`: described above.
- `scripts/faucet_check.py`: prints wallet address + balance only.

---
# v2 additions (Phase 1 of demo_video2, read-only, 2026-10-21): amendment V2, version history, download, archive
Read from `documents/router.py`, `documents/workflow.py`, `documents/service.py`, `versions/service.py`, `verify/service.py`,
`reports/service.py`, `core/rbac.py` and the frontend pages `DocumentDetails`, `AmendmentRequest`, `VersionHistory`, `Verification`.

## 10. Amendment (V2) flow – who, geofence, endpoints, state
| Step | UI | Endpoint | Who (RBAC) | Geofence | Document status | Version rows | Audit |
|---|---|---|---|---|---|---|---|
| 1 Request | Document Details → **Request amendment** → `/documents/:id/amend`, reason textarea | `POST /documents/{id}/amend` `{reason}` | `document:amend` = **Authorized Staff or Legal Officer** (not Reviewer, Auditor, Admin) | **yes** (`document_amend`) | ACTIVE → **AMENDMENT_REQUESTED** (only legal from ACTIVE; else 409 `ILLEGAL_TRANSITION`) | none changed; V1 stays ACTIVE and stays `documents.current_version_id` | `AMEND_REQ` (+reason) |
| 2 Upload V2 | same page after step 1: "Upload amended version" | `POST /documents` multipart with `amend_of=<id>` (title/type/classification copied from the document) | `document:amend` and clearance for the doc | **yes** (`document_upload`) | AMENDMENT_REQUESTED → **DRAFT** | **new insert-only row** V2: `version_no`=2, `prev_version_hash` = **V1.sha256**, own `storage_key`, status DRAFT, `uploaded_by` = V2 uploader. V1 untouched | `UPLOAD` (`meta.amend=true`, `version_no=2`) |
| 3 Classification | – | – | – | – | – | a different classification on the amend form is refused: `CLASSIFICATION_IMMUTABLE`, audited `CLASSIFICATION_CHANGE_REFUSED` | |
| 4 Submit → review → approve | normal buttons | `/submit`, `/review`, `/approve` act on the **highest `version_no`** (V2), not on `current_version_id` | V2's uploader submits; reviewer ≠ V2 uploader; approver ≠ V2 uploader (`MAKER_CHECKER_VIOLATION`) | approve only | DRAFT → SUBMITTED → PENDING_APPROVAL → APPROVED → BLOCKCHAIN_ANCHORED → **ACTIVE** | V2 gets its own `blockchain_anchors` row (**second Sepolia tx**, key `keccak256(documentId, 2)`) | SUBMIT, REVIEW_START, REVIEW_PASS, APPROVE, ANCHOR_OK, ACTIVATE |
| 5 What happens to V1 | Version History | inside `complete_promotion` | system | – | – | when V2 is confirmed: V2 → **ACTIVE**, `documents.current_version_id` → V2, and V1 (the other ACTIVE version) → **SUPERSEDED**. Hash, key and anchor of V1 are untouched | `ANCHOR_OK` (target = V2), `ACTIVATE` |

Notes: while V2 is in review, V1 stays live and downloadable (`current_version_id` is repointed only at final activation). A reviewer's "changes requested" on V2
loops the document back to DRAFT and the same page accepts a corrected file (V3, no new amend request).
The **document** itself never gets status SUPERSEDED, only version rows do (the Repository filter lists "SUPERSEDED" but no code path sets it). `docs/API.md:52` says archive accepts
"ACTIVE/SUPERSEDED"; the code accepts ACTIVE only. That is a doc/code mismatch to flag (CLAUDE.md "before making changes" #5), not to fix in this task.

## 11. Version history (`/documents/:id/versions` → `GET /documents/{id}/versions`)
- Needs only `document:view` + clearance (hidden document → 404). Lists newest first: **V# + status badge** (DRAFT … ACTIVE / SUPERSEDED), a **CONFIRMED** badge if anchored,
  upload time, **SHA-256 (truncated)**, size, MIME, **Prev. hash (truncated; "—" for V1)**, buttons **Verify** and (if anchored) **View on-chain**.
- The **parent link** is the field `prev_version_hash`, labelled "Prev. hash": for V2 it equals V1's SHA-256. There is **no "current" label** in the UI: current = the ACTIVE badge
  (= `documents.current_version_id`). No uploader name is shown, and no `parent_version_id` field exists.
- The UI truncates hashes, so showing the full parent link needs a labelled supplementary view.

## 12. Download
- `GET /documents/{id}/download` → `{url, expires_in_sec}` (pre-signed GET, TTL `STORAGE_PRESIGN_TTL_SEC`, default 60 s). The API never streams bytes.
- RBAC: `document:view` (**every role has it**) + clearance (hidden → 404 `document_not_found`, audited `ACCESS_DENIED`). **Geofenced** (`document_download`): outside the zone → 403 `GEOFENCE_DENIED` (audited, with location); low accuracy → 422 `LOCATION_LOW_CONFIDENCE` (application log only).
- Always the **current** version (`documents.current_version_id`); there is **no per-version download**. Before V2 is ACTIVE it returns V1; after, V2. A document with no current version → 404.
- **Audited**: action `ACCESS`, target = document, `meta.version_id`, `ip`. The UI Download button calls `window.open(url)` (a new browser tab).
- The hash check is not an app feature: the supplementary step downloads the pre-signed URL, SHA-256s the bytes and compares with `document_versions.sha256`.
- Real denials available: (a) a role whose clearance is below the document → 404 (e.g. the throwaway PUBLIC viewer); (b) a request from outside the zone → `GEOFENCE_DENIED`. No role is refused by RBAC alone.

## 13. Archive
- `POST /documents/{id}/archive`, no body, **no reason field**, **not geofenced**. UI: Document Details → red **Archive** button (shown only when status = ACTIVE and the role has `document:archive`).
- Allowed: **Administrator or Legal Officer** with clearance for the document (an Administrator at INTERNAL gets 404 on a CONFIDENTIAL document). Only from **ACTIVE** (else 409 `ILLEGAL_TRANSITION`).
- Effect: `documents.status` = ARCHIVED and `updated_at`; audit `ARCHIVE`. **Versions, anchors and files are untouched**; `retention_until` is not set.
- **Not reversible in the app**: there is no un-archive or restore route or service in the backend (searched). Only direct database editing could change it.
- Visibility: the default list (Dashboard count, Repository, search) uses `status != ARCHIVED`; the document is found with Repository status filter **Archived**. The document page still opens and **verify still works** on it (verify never checks document status).
- Reports (`GET /reports/summary`) count archived in "Documents by status" and print "N documents you can access in total, including M archived. The Dashboard and Document Repository show N−M …".
  Reports counts are clearance-filtered: an administrator (INTERNAL) only counts documents up to INTERNAL, so **the live document must be INTERNAL for the archived count to move on the admin Reports page.**

## 14. Verification of a superseded version
`verify_version` does not read document or version status except to decide whether the database "claims anchored" (SUPERSEDED counts as post-anchor). It re-reads V1's stored bytes, recomputes,
and compares with V1's stored hash and the on-chain hash for (documentId, 1). So **V1 still returns VERIFIED after V2 is ACTIVE**. The Verification page has **no special "superseded" wording**;
the only place the app says SUPERSEDED is the grey status badge in Version History. A MISMATCH on any version sets the **document-level** `integrity_flag=TAMPERED` (banner on Document Details).
That flag is **not** cleared by a later VERIFIED; only the Administrator-only "Clear integrity flag" (re-verifies every anchored version first, reason of 10+ characters, audited `INTEGRITY_CLEARED`) clears it.
The flag does not block submit, review, approve or amend. Verify also works on an ARCHIVED document.

## 15. Observed while recording (2026-10-22, demo v2)
- **Download enforcement order:** token -> role -> zone -> document/clearance. A user with no assigned zone gets 403 `GEOFENCE_DENIED` on `GET /documents/{id}/download`; only a zone-assigned, below-clearance user reaches the 404.
- **Stale location:** geofenced actions fail with 422 `LOCATION_STALE` when the browser's reading is older than the freshness limit (120 s here); the refusal happens before anything is approved.
- **Hidden document in the UI:** the 404 page retries the request, so one visit writes several `ACCESS_DENIED` rows.
- **Audit page document filter** uses the default (non-archived) document search, so archived documents cannot be picked there; `View audit trail` on the document page still works for them.
- **Approval anchoring** confirmed within the request window both times (V1 block 11966398, V2 block 11966608).
