# Threat Model — GeoLegalVault

This document states the assets, threats, mitigations, and — deliberately — the residual
risks and honest limitations of the system. Per Guardrail #6: **geofencing is a policy
control, not a cryptographic guarantee; blockchain anchoring is the actual tamper-evidence
guarantee.** Nothing here or anywhere else in the codebase claims "military-grade,"
"tamper-proof," "unhackable," or "guaranteed location."

## Assets

| Asset | Why it matters | Where it lives |
|---|---|---|
| Document bytes | Confidential content (contracts, NDAs, memos) | Cloudflare R2 / MinIO — private bucket, never on-chain |
| Document metadata + version lineage | Provenance, chain of custody | MongoDB (`documents`, `document_versions`) |
| SHA-256 anchors | The externally-verifiable integrity proof | Sepolia (`DocumentAnchor` contract) + `blockchain_anchors` |
| User credentials | Account takeover surface | `users.password_hash` (Argon2id) |
| Service-wallet private key | Controls all future anchoring | Backend env/secret store only |
| Audit log | Independent record of who did what, where | `audit_logs` (append-only) |
| JWT access/refresh tokens | Session identity | In-memory (frontend) / httpOnly cookie |

## Threat table (STRIDE-adjacent, Plan Part 14)

Format: **Threat → Impact → Likelihood → Mitigation → Residual risk.**

| # | Threat | Impact | Likelihood | Mitigation (as implemented) | Residual |
|---|---|---|---|---|---|
| 1 | Credential theft / weak passwords | Account takeover | Med | Argon2id hashing, per-email login rate limit (`modules/auth/service.py`), generic 401 (no user enumeration) | Low |
| 2 | JWT theft (XSS) | Impersonation | Med | Short access-token TTL (15 min default), refresh token only in an httpOnly cookie, access token kept in memory (never `localStorage`) on the frontend | Low-Med |
| 3 | JWT forgery / alg confusion | Full bypass | Low | Signature verified, algorithm pinned to HS256, `alg: none` explicitly rejected (`core/security.py`) | Low |
| 4 | Privilege escalation | Unauthorized ops | Med | Deny-by-default RBAC (`core/rbac.py`); role is read fresh from the DB user on every request, not trusted from JWT claims alone | Low |
| 5 | IDOR (guessed document/version IDs) | Data exposure | Med | Every read/write re-checks the caller's permission + (for sensitive ops) geofence; ObjectIds are not sequential/guessable | Low |
| 6 | Broken access control | Wide exposure | Med | Central `require(permission)` dependency on every protected route; authz-matrix test (`tests/api/test_authz_matrix.py`) asserts allow/deny per role × endpoint | Low |
| 7 | Malicious file upload | Malware distribution | Med | Size cap, content-type allow-list, magic-byte detection cross-checked against the claimed type (`modules/documents/service.py::validate_upload`); files are never served inline, only via pre-signed download | Med — no ClamAV scan (cut per the plan's priority list; MIME/magic validation only) |
| 8 | Path traversal in storage keys | Overwrite/leak | Low | Storage key is always server-generated (`docs/{document_id}/v{n}`) — the client's filename is never used as a path | Low |
| 9 | Object-storage misconfiguration (public bucket) | Mass leak | Med | Bucket is private; the only egress path is a short-lived pre-signed GET URL (`STORAGE_PRESIGN_TTL_SEC`, default 60 s); the API never proxies bytes | Low |
| 10 | NoSQL injection | Data leak/bypass | Med | All queries built via Motor's typed filter dicts from validated Pydantic input — no string-built queries, no `$where`, no raw user JSON passed into a filter | Low |
| 11 | API abuse / brute force | DoS, credential stuffing | Med | Global per-IP rate limit (`core/rate_limit.py`, default 120 req/min) plus the auth module's own tighter per-email limit | Med — in-memory, per-process (see Limitation below) |
| 12 | Replay attacks | Repeated ops | Low | HTTPS in every non-local deployment; geofence checks include a freshness window (`GEO_FRESHNESS_MAX_SEC`); the contract rejects re-anchoring the same (doc, version) | Low |
| 13 | Blockchain service-key compromise | False anchors | Low | Key lives only in platform secret storage (Render env), never in git/frontend/logs; wallet holds only faucet ETH; Verify cross-checks recomputed vs. stored vs. on-chain, so a single false anchor alone can't produce a false VERIFIED for an existing document | Med |
| 14 | GPS spoofing | Geofence bypass | High | Fail-closed on low accuracy / stale timestamp (422); server never trusts a client "inside" flag — **acknowledged prototype limitation, see below** | **High (accepted)** |
| 15 | Geofence bypass via a client-supplied flag | Bypass | Med | The server independently runs the `$geoIntersects` query on every sensitive request; no endpoint reads a client "allowed" field at all | Low |
| 16 | DB tampering (admin/insider) | Silent alteration | Med | An altered file (or an altered stored hash) fails the next Verify against the immutable on-chain hash; `audit_logs` is append-only | Low (detectable, not prevented) |
| 17 | Cloud account compromise | Broad | Low | Least-privilege scoped keys per Deployment guide (R2 token, Atlas user); out of this codebase's control otherwise | Med |
| 18 | Insider threat | Misuse | Med | Maker-checker separation (`enforce_maker_checker`: approver ≠ uploader), Auditor is read-only everywhere and sees everything | Med |
| 19 | Audit log manipulation | Cover tracks | Med | Append-only collection, no update/delete API path anywhere in `modules/audit` | Low-Med — no periodic hash-chaining of log batches (optional hardening, not implemented) |
| 20 | Secrets in git | Full compromise | Med | `.gitignore` excludes `.env`/`.env.*`; only `.env.example` (placeholders) is committed; `APP_ENV != development` fails startup if any required secret is still a placeholder | Low |

## Cross-cutting controls

TLS in transit (platform-terminated on Vercel/Render); encryption at rest is a storage-
platform property (R2 encrypts by default; local MinIO does not — see `services/storage.py`
docstring for why SSE parameters aren't set explicitly); Argon2id for all passwords; input
validation via Pydantic at every API boundary; the enforcement pipeline
**TLS → JWT → RBAC → geofence → input/file validation → action → audit** runs, in that
order, on every sensitive endpoint (Guardrail #5); security response headers
(`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Cache-Control: no-store`,
HSTS outside local dev) are set on every response (`core/security_headers.py`).

## Honest limitations (state these openly — do not paper over them)

1. **Browser GPS is spoofable.** DevTools location override, fake-GPS mobile apps, and
   VPN+coordinate spoofing can all make a client report coordinates it isn't physically at.
   The system does not attempt hardware GPS attestation (explicitly out of scope). Geofencing
   here is **defense-in-depth policy**, not an anti-spoof control — say so in every report,
   viva, and demo slide.
2. **In-memory rate limiting is per-process.** With multiple gunicorn workers or multiple
   deployed instances, an attacker distributing requests across workers/instances sees a
   higher effective limit than the configured number. A production deployment beyond
   prototype scale would need a shared store (Redis) instead.
2b. **Malware scanning is not implemented.** Upload validation is MIME + magic-byte +
   size only; a well-formed malicious PDF/DOCX would pass. ClamAV integration is a named
   Level-3 candidate (Plan Part 26), cut here per the project's own priority order.
3. **Custodial signing.** One backend service wallet signs every anchor. This is a known,
   accepted trade-off (Plan Part 18) chosen over per-user MetaMask for demo feasibility — it
   means anchoring integrity depends on that one key's confidentiality, not on distributed
   user consent.
4. **Testnet impermanence.** Sepolia is a testnet; RPC providers rate-limit free tiers and a
   testnet could in principle reset. Every anchor's tx hash and block number are also stored
   locally (`blockchain_anchors`) precisely so a demo/report never depends on the chain being
   reachable at read time — but a full testnet reset would still orphan historical on-chain
   reads until re-anchored.
5. **On-chain proof is narrower than it sounds.** An anchor proves *"this exact hash existed
   under this documentId/version at this block time, submitted by the service wallet"* — it
   does **not** prove authorship, that the uploader was honest, or that the off-chain party
   names in the document are real. It proves the file has not changed *since anchoring*.
6. **Small scale, not load-tested.** Performance targets (`SRS.md` §5) are prototype targets
   checked informally, not validated under sustained concurrent load.

These limitations are the point of an honest threat model, not an embarrassment to hide —
the closing slide of `DEMO_SCRIPT.md` states them explicitly.
