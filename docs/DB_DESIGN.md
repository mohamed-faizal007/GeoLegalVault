# Database Design — GeoLegalVault (MongoDB)

Single database (`MONGODB_DB`, default `geolegalvault`), no sharding, no separate services —
one Motor (async) client per process. Indexes are created idempotently at startup by
`backend/app/core/db.py::ensure_indexes()`, the single source of truth for every index in
this document; if the two ever disagree, the code wins.

## Why MongoDB

Flexible schema for metadata that varies by document type, plus a genuine (not cosmetic)
reason: native `2dsphere` geospatial indexing for the geofence point-in-polygon query that
gates every sensitive operation (Plan Part 0.1).

## Collections

### `users`
| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `email` | string | unique index |
| `password_hash` | string | Argon2id; never returned by any API response |
| `name` | string | |
| `role` | string | one of `ADMINISTRATOR, LEGAL_OFFICER, REVIEWING_OFFICER, AUTHORIZED_STAFF, AUDITOR` |
| `assigned_geofence_ids` | string[] | geofences this user's sensitive ops are scoped to |
| `is_active` | bool | deactivation, never hard-delete |
| `created_at`, `last_login` | datetime | |

**Indexes:** `email` (unique).

### `refresh_sessions`
Tracks refresh-token rotation and enables reuse detection (a presented token whose session
already has `replaced_by` set means theft — the whole `family` is revoked).

| Field | Type |
|---|---|
| `jti` | string (unique) |
| `family` | string |
| `user_id` | string |
| `revoked` | bool |
| `replaced_by` | string \| null |
| `created_at`, `expires_at` | datetime |

**Indexes:** `jti` (unique), `family`.

### `geofences`
| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `name` | string | |
| `region` | GeoJSON Polygon | `[lng, lat]` order; validated closed ring, ≤ `MAX_POLYGON_VERTICES`, coordinate-range checked (catches an accidental lat/lng swap) |
| `center`, `radius_m` | GeoJSON Point, float \| null | optional alternate representation |
| `active` | bool | deactivate, never hard-delete a fence in use |
| `created_at` | datetime | |

**Indexes:** `region` (2dsphere), `center` (2dsphere).

**Geospatial query** (`services/geofence.py::check_location`): `region: {$geoIntersects: {$geometry: {type: "Point", coordinates: [lng, lat]}}}`, scoped to `_id in user.assigned_geofence_ids` and `active: true`. This is the *only* authorization signal ever trusted for location — a client-supplied "inside=true" flag is never read.

### `documents`
| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `title`, `doc_type`, `classification` | string | |
| `owner_id` | ObjectId | the uploader |
| `status` | string | lifecycle state — see Plan Part 5 |
| `current_version_id` | ObjectId \| null | repointed only at final activation (never mid-review) |
| `tags` | string[] | |
| `integrity_flag` | string \| null | set to `"TAMPERED"` by Verify on a MISMATCH; cleared only by manual investigation |
| `anchor_pending_alert` | bool | surfaced when anchoring exhausted its retries |
| `retention_until` | datetime \| null | |
| `created_at`, `updated_at` | datetime | |

**Indexes:** `status`; `owner_id`; compound `{status, doc_type}`; text index on `{title, tags}`.

**Mutation discipline:** `documents/service.py` exposes only whitelisted setters
(`update_status`, `set_current_version`, `set_anchor_alert`, `set_integrity_flag`) —
nothing writes arbitrary fields on an existing document.

### `document_versions` (insert-only)
| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `document_id` | ObjectId | |
| `version_no` | int | 1, 2, 3, … |
| `sha256` | string | computed server-side on the exact stored bytes |
| `prev_version_hash` | string \| null | the prior version's `sha256`; null on V1 — the version chain |
| `storage_key` | string | server-generated (`docs/{document_id}/v{n}`), never the client filename |
| `size_bytes`, `mime` | int, string | |
| `status` | string | mirrors the owning document's lifecycle stage for this version |
| `uploaded_by`, `uploaded_at` | ObjectId, datetime | |
| `anchored` | bool | |
| `anchor_id` | ObjectId \| null | set once the anchor is confirmed |

**Indexes:** `{document_id, version_no}` (unique compound — the only mechanism preventing a
duplicate version number for one document), `sha256`.

**Mutation discipline:** the only write paths are `insert_version` and two whitelisted
updates — `update_status` and `mark_confirmed_anchor` (which sets `anchored`/`anchor_id`/
`status` together). Content, hash, and `storage_key` are fixed forever once inserted
(Guardrail #7) — there is no code path that can alter them.

### `blockchain_anchors`
| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `document_id`, `version_id` | ObjectId | |
| `sha256` | string | the hash actually sent on-chain |
| `event_type` | int | matches the contract's `eventType` |
| `tx_hash` | string \| absent | **absent** (not null) on a send failure — see index note below |
| `block_number` | int \| null | set on confirmation |
| `contract_address`, `network` | string | |
| `status` | string | `PENDING \| CONFIRMED \| FAILED` |
| `error` | string \| null | |
| `created_at`, `confirmed_at` | datetime | |

**Indexes:** `tx_hash` (unique, **sparse**), `version_id`. The index is sparse because a
send that never reaches the RPC (chain unreachable) records a row with `tx_hash` **entirely
omitted**, not set to `null` — an explicit `null` would still be indexed and a second failed
attempt would collide on the unique constraint; omitting the key avoids that entirely.

### `verification_records`
Append-only log of every Verify click — the audit trail specific to the integrity check
itself (distinct from `audit_logs`, which also gets a `VERIFY_PASS`/`VERIFY_FAIL` entry per
check).

| Field | Type |
|---|---|
| `version_id` | ObjectId |
| `requested_by` | ObjectId |
| `recomputed_hash` | string |
| `stored_hash` | string |
| `onchain_hash` | string \| null |
| `result` | `VERIFIED \| MISMATCH \| NOT_ANCHORED` |
| `created_at` | datetime |

**Indexes:** `{version_id, created_at desc}`.

### `audit_logs` (append-only)
| Field | Type | Notes |
|---|---|---|
| `actor_id` | ObjectId \| string | usually a user id; `"SYSTEM"` for system-triggered actions (e.g. `ANCHOR_OK`), or a raw email for a pre-authentication failed login |
| `action` | string | `LOGIN_SUCCESS/FAILURE, GEOFENCE_DENIED, UPLOAD, SUBMIT, REVIEW_*, APPROVE, ANCHOR_OK/ANCHOR_FAIL, AMEND_REQ, ARCHIVE, VERIFY_PASS/VERIFY_FAIL/VERIFY_NOT_ANCHORED, …` |
| `target_type`, `target_id` | string, ObjectId \| string | |
| `result` | string | `SUCCESS \| FAILED \| MISMATCH \| ...` |
| `ip` | string \| null | |
| `location` | GeoJSON Point \| absent | present only on geofence-relevant events; **never written as an explicit null** so the field behaves as sparse without the flag |
| `meta` | object | freeform context (e.g. `{comment: ...}`, `{tx_hash: ...}`) |
| `created_at` | datetime | |

**Indexes:** `{actor_id, created_at desc}`, `action`, `location` (2dsphere).

**Write discipline:** `modules/audit/service.py` exposes exactly one write function
(`record`, an insert) and one read function (`list_audit_logs`); there is no update or
delete path anywhere, and the router only exposes `GET /audit`.

## Cross-collection integrity (application-enforced, not a Mongo transaction)

MongoDB here runs as a single replica-less instance (Atlas M0 / local `mongo:7`), so
multi-document ACID transactions aren't assumed. Consistency between `documents` and
`document_versions` is instead enforced procedurally:

- **Upload:** `documents` is inserted, then the V1 `document_versions` row; if the version
  insert fails, the `documents` row is deleted in the same call (`documents/service.py::
  create_document_with_v1`) — no orphan document metadata.
- **Approve → anchor:** `documents.status` and `document_versions.status` are updated in a
  fixed sequence per Plan Part 5's transition table; an anchor failure never rolls either
  back — the document simply stays `APPROVED` (pending anchor), which is itself a valid,
  intentional state, not a partial-write bug.

## Retention

Archival flips `documents.status` to `ARCHIVED` (hidden from the default repository list,
which excludes `ARCHIVED` unless a caller explicitly filters on it) — every version,
anchor, and verification record is retained untouched. `document_versions` and
`audit_logs` are never pruned by the application.
