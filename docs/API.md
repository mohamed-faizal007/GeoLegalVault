# API Reference — GeoLegalVault

Base path: `/api/v1`. Interactive docs (auto-generated from the FastAPI schema, always the
most current source of exact request/response shapes) are served at `GET /docs`
(Swagger UI) and `GET /openapi.json` on any running instance — this document is a stable
map on top of that, plus the auth flow and error catalogue that OpenAPI doesn't narrate.

## Authentication

1. `POST /auth/login` with `{email, password}` → `{access_token, expires_in_min}` in the
   JSON body, plus a `refresh_token` set as an **httpOnly, Secure, SameSite=Strict** cookie
   scoped to `/api/v1/auth`. The access token is never in a cookie — the frontend keeps it
   in memory only and sends it as `Authorization: Bearer <access_token>` on every
   subsequent request.
2. Access tokens are short-lived (`JWT_ACCESS_TTL_MIN`, default 15 min). When one expires,
   call `POST /auth/refresh` (no body — the browser sends the refresh cookie
   automatically) to get a new access token and a **rotated** refresh cookie.
3. Presenting an already-rotated-out refresh token is treated as token theft: the entire
   session family is revoked and the caller must log in again.
4. `POST /auth/logout` revokes the current refresh session and clears the cookie.

Login/refresh failures are always a generic `401` (`"Invalid email or password"` /
`"Invalid refresh token"`) — the API never reveals whether an email exists.

## Endpoints

`Auth` column names the permission from `core/rbac.py::ROLE_PERMISSIONS` (see
`THREAT_MODEL.md` / `SRS.md` §3 for the full role matrix); "any" means authenticated-only,
no specific permission.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/login` | none | Authenticate, get tokens |
| POST | `/auth/refresh` | refresh cookie | Rotate access token |
| POST | `/auth/logout` | any | Revoke current session |
| POST | `/users` | `users:manage` | Create a user |
| GET | `/users` | `users:manage` | List users (paginated) |
| PATCH | `/users/{id}` | `users:manage` | Update/deactivate a user |
| POST | `/geofences` | `geofence:manage` | Create a geofence |
| GET | `/geofences` | `geofence:manage` | List geofences |
| GET | `/geofences/{id}` | `geofence:manage` | Get one geofence |
| PATCH | `/geofences/{id}` | `geofence:manage` | Edit/deactivate a geofence |
| POST | `/documents` | `document:upload` + geofence | Upload a new document (multipart: file + metadata + location) |
| GET | `/documents` | `document:view` | Search/list documents (paginated, filterable) |
| GET | `/documents/{id}` | `document:view` | Document metadata |
| GET | `/documents/{id}/download` | `document:view` + geofence | Short-lived pre-signed download URL |
| GET | `/documents/{id}/versions` | `document:view` | Full version lineage |
| POST | `/documents/{id}/submit` | `document:submit`, owner only | DRAFT → SUBMITTED |
| POST | `/documents/{id}/review` | `review:perform`, reviewer ≠ uploader | Review decision (approve-to-next-stage or request changes) |
| POST | `/documents/{id}/approve` | `approve:perform` + geofence, approver ≠ uploader | Approve → auto-triggers anchoring |
| POST | `/documents/{id}/amend` | `document:amend` + geofence | Start an amendment (ACTIVE → AMENDMENT_REQUESTED) |
| POST | `/documents/{id}/archive` | `document:archive` | Archive (ACTIVE/SUPERSEDED → ARCHIVED) |
| POST | `/verify/{version_id}` | `verify:perform` | Run the 3-way integrity check |
| GET | `/verify/{version_id}/history` | `verify:perform` or `audit:view` | Past verification records for a version |
| GET | `/blockchain/anchor/{version_id}` | `document:view` | Stored + on-chain anchor record, with Etherscan link |
| GET | `/audit` | `audit:view` | Query the audit log (filterable, paginated) |
| GET | `/reports/summary` | `audit:view` | Aggregate counts (status, anchor success rate, verifications, geofence denials) |
| GET | `/health` | none | `{status, mongo, storage, chain}` reachability |

There is deliberately **no** endpoint that lets a user trigger anchoring directly —
anchoring is only ever a system-triggered side effect of `POST /documents/{id}/approve`
(Guardrail #3).

### Location payload (sensitive endpoints)

Endpoints marked "+ geofence" above require `{lat, lng, accuracy, timestamp}` alongside
the request (form fields on the multipart upload, JSON body fields elsewhere). The server
independently runs the `$geoIntersects` check — it never reads or trusts any client-sent
"inside the fence" flag.

### Example: upload

```http
POST /api/v1/documents  (multipart/form-data)
file=@nda.pdf; title=Vendor NDA; doc_type=NDA; classification=CONFIDENTIAL; tags=nda,vendor
lat=11.67; lng=78.15; accuracy=25; timestamp=2026-09-01T10:00:00Z

201 {"document_id": "...", "version_id": "...", "status": "DRAFT", "sha256": "a1b2..."}
403 {"error": {"code": "GEOFENCE_DENIED", "message": "..."}}
422 {"error": {"code": "MIME_MISMATCH", "message": "..."}}
```

### Example: verify

```http
POST /api/v1/verify/{version_id}

200 {"result": "VERIFIED",  "recomputed": "a1b2...", "stored": "a1b2...", "onchain": "a1b2...", "tx_hash": "0x...", "etherscan_url": "https://sepolia.etherscan.io/tx/0x..."}
200 {"result": "MISMATCH",  "recomputed": "zz99...", "stored": "a1b2...", "onchain": "a1b2...", "tx_hash": "0x...", "etherscan_url": "..."}
200 {"result": "NOT_ANCHORED", "recomputed": "a1b2...", "stored": "a1b2...", "onchain": null, "tx_hash": null, "etherscan_url": null}
```
`MISMATCH` is a `200`, not an error — it's a successful check that found tampering.

## Error format

Most endpoints (everything under `documents`, `versions`, `geofences`, `verify`,
`blockchain`) raise a typed `AppError` subclass and get the shared envelope:

```json
{"error": {"code": "GEOFENCE_DENIED", "message": "human-readable detail"}}
```

The `auth` and `users` routers instead raise plain FastAPI `HTTPException`s, which render
as `{"detail": "..."}` — this asymmetry is real (not a documentation gap): auth failures
deliberately return a generic, uninformative detail string (no user enumeration), where
the structured `{code, message}` shape elsewhere exists precisely so a frontend can branch
on `code` (e.g. show "you're outside the authorized location" for `GEOFENCE_DENIED` vs.
"you don't have permission" for `FORBIDDEN`).

### Error code catalogue

| Code | HTTP | Meaning |
|---|---|---|
| `FORBIDDEN` | 403 | RBAC: caller's role lacks the required permission |
| `MAKER_CHECKER_VIOLATION` | 403 | Approver/reviewer is the same person as the uploader |
| `GEOFENCE_DENIED` | 403 | Caller is outside every geofence assigned to them |
| `LOCATION_LOW_CONFIDENCE` | 422 | Reported GPS accuracy worse than `GEO_ACCURACY_MAX_M` |
| `LOCATION_STALE` | 422 | Reported location timestamp older than `GEO_FRESHNESS_MAX_SEC` |
| `INVALID_LOCATION` | 422 | Malformed/out-of-range coordinates |
| `FILE_TOO_LARGE` | 413 | Upload exceeds `MAX_UPLOAD_MB` |
| `UNSUPPORTED_MEDIA_TYPE` | 422 | Claimed content-type isn't on the allow-list |
| `MIME_MISMATCH` | 422 | Magic-byte detection disagrees with the claimed content-type |
| `STORAGE_UNAVAILABLE` | 503 | Object storage unreachable (upload/verify) |
| `ILLEGAL_TRANSITION` | 409 | Lifecycle transition not valid from the document's current status |
| `VALIDATION_REQUIRED` | 422 | A required field for this transition is missing (e.g. a "changes requested" comment) |
| `NOT_FOUND` | 404 | Document/version doesn't exist |
| `RATE_LIMITED` | 429 | Global per-IP rate limit exceeded (`core/rate_limit.py`) |
| — (plain `detail`) | 401 | Auth: invalid/expired/malformed token, no refresh token, invalid credentials |
| — (plain `detail`) | 403 | Auth: account deactivated |
| — (plain `detail`) | 429 | Auth: too many failed login attempts for this email |

## Pagination

List endpoints accept `?page=&limit=` and return `{items, page, limit, total}`.
