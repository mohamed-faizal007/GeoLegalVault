# MongoDB collections (database `geolegalvault_demo` (demo run; the dev DB `geolegalvault` is never touched))

Field lists come from a read-only look at the live dev database on 2026-10-21 (keys of one real row each; no values, no password
hashes) cross-checked against the code. `password_hash` exists on `users` and must never be shown on screen.

| Collection | Written by (only these paths) | Key fields | Class |
|---|---|---|---|
| `users` | `users/service.py` (create, PATCH), `auth/service.py` (`last_login`) | `email`, `name`, `role`, `clearance`, `assigned_geofence_ids`, `is_active`, `password_hash`*, `last_login`, `created_at` | authoritative |
| `geofences` | `geofences/service.py` | `name`, `region` (GeoJSON Polygon, **[lng, lat]**), `center`, `radius_m`, `active`, `created_at` | authoritative |
| `documents` | `documents/service.py`, `workflow.py` | `title`, `doc_type` (free text), `classification` (immutable), `owner_id`, `status`, `current_version_id`, `tags`, `retention_until`, `anchor_pending_alert`, `integrity_flag` (`TAMPERED`/`UNCONFIRMED`/none), `review_feedback`, `anchor_retry` | authoritative (the *state*) |
| `document_versions` | **insert-only** (`versions/service.py::insert_version`; only `status`/anchor link may be updated) | `document_id`, `version_no`, `sha256`, `storage_key`, `mime`, `size_bytes`, `uploaded_by`, `uploaded_at`, `prev_version_hash`, `status`, `anchored`, `anchor_id` | authoritative (the *fingerprint*) |
| `blockchain_anchors` | `blockchain/service.py` (API at approval, or the worker) | `document_id`, `version_id`, `sha256`, `event_type`, `network`, `contract_address`, `tx_hash`, `block_number`, `status` (PENDING/CONFIRMED/FAILED), `error` (fixed code, never raw text), `created_at`, `confirmed_at` | derived / a record of the chain; the chain is the real evidence |
| `verification_records` | `verify/service.py` (append-only, one row per verify call) | `version_id`, `requested_by`, `recomputed_hash`, `stored_hash`, `onchain_hash`, `result`, `reason`, `created_at` | audit-like history |
| `audit_logs` | `audit/service.py::record` (append-only) | `actor_id`, `action`, `target_type`, `target_id`, `result`, `ip`, `meta`, `created_at` (+location on geofence denials) | audit. **No hash chain yet (CMP-01 pending)**, so a person with DB write access could alter it |
| `refresh_sessions` | `auth/service.py` | refresh-token sessions per login | operational |
| `login_rate_limits` | `auth/service.py` | failure counter per email (5 failures → lockout window) | operational |
| `worker_heartbeats` | `workers/heartbeat.py` | one liveness document read by `/health` | operational |

## ID links
`documents._id` ← `document_versions.document_id`; `document_versions._id` ← `blockchain_anchors.version_id`, `verification_records.version_id`;
`documents.current_version_id` → the ACTIVE version; `document_versions.anchor_id` → `blockchain_anchors._id`;
`document_versions.storage_key` → object `docs/<documentId>/v<n>-<sha256>` in the private bucket `geolegalvault-dev`;
`audit_logs.target_id` → document / version / user `_id`.
On-chain key is `keccak256(documentId, version)`, i.e. the string form of `documents._id` plus the version number.

## What lives where
| Place | Holds | Does not hold |
|---|---|---|
| MongoDB | users, fences, document state, version metadata + hash, anchor records, audit | file bytes |
| RustFS / R2 (S3) | the file bytes, under a server-made key | metadata about who/why |
| Sepolia contract | `{hash, version, eventType, timestamp}` per (documentId, version) | file, name, any person |

## Audit entries a normal demo run creates (by action name)
LOGIN_SUCCESS / LOGIN_FAILURE, GEOFENCE_DENIED (outside zone), UPLOAD, SUBMIT, REVIEW_START, REVIEW_PASS, APPROVE, ANCHOR_OK, ACTIVATE,
ACCESS (download), ACCESS_DENIED (below-clearance attempt on an existing document), VERIFY_PASS, VERIFY_FAIL, USER_CREATE.
A low-accuracy or stale reading is rejected **before** the zone check and is logged to the application log, not to `audit_logs` (see `geofence.py`).
Rejected self-approval returns `MAKER_CHECKER_VIOLATION` (403); whether it creates an audit row is checked during recording and reported in FEATURES_DEMONSTRATED.md.

## Supplementary-view rule
Any view of this data in the video is produced by `demo_video2/scenes/supp.py` and the scene scripts: read-only queries with a projection that excludes
`password_hash` and any secret, labelled "Supplementary view – not the app UI".

---
## v2 additions (amendment, version history, download, archive)
| Collection | Field | What it shows in the amendment/archive story |
|---|---|---|
| `document_versions` | `version_no` (1, 2), `prev_version_hash` | V2's `prev_version_hash` equals V1's `sha256` (the parent link; V1 has `null`). There is no `parent_version_id` field |
| `document_versions` | `status` | V1: ACTIVE → **SUPERSEDED** when V2 becomes ACTIVE; V2: DRAFT → … → ACTIVE. The only mutable fields are `status`, `anchored`, `anchor_id` |
| `document_versions` | `anchored`, `anchor_id`, `storage_key` | each version has its own anchor and its own object `docs/<documentId>/v<n>-<sha256>` |
| `documents` | `current_version_id` | V1 until V2 is ACTIVE, then V2 (repointed once, at activation); the download serves this version |
| `documents` | `status` | ACTIVE → AMENDMENT_REQUESTED → DRAFT … ACTIVE → **ARCHIVED**; the document is never SUPERSEDED |
| `documents` | `integrity_flag`, `integrity_cleared{by,at,reason}` | TAMPERED after a MISMATCH; survives a later VERIFIED; cleared only by the admin action |
| `blockchain_anchors` | one row per (document, version) | V1 and V2 each have a CONFIRMED row with their own `tx_hash` / `block_number` (two Sepolia transactions) |
| `audit_logs` | `AMEND_REQ` (meta.reason), `UPLOAD` (meta.amend, version_no), `ACCESS` (download, meta.version_id), `ARCHIVE`, `ACCESS_DENIED`, `GEOFENCE_DENIED`, `INTEGRITY_CLEARED` | the new rows this storyline creates |
| `verification_records` | one row per verify call per version | V1 and V2 each get a VERIFIED row; V1 also gets a MISMATCH row while tampered |
