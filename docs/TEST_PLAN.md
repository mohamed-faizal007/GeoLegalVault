# Test Plan — GeoLegalVault

## Strategy

Test at the layer where a bug is cheapest to catch, per Plan Part 20:

| Layer | Tool | What it covers |
|---|---|---|
| Unit | pytest | Hashing correctness, geofence point-in-polygon, RBAC map, lifecycle transitions, security primitives |
| Integration | pytest + httpx + real local Mongo/MinIO/Hardhat | Upload→store→hash→metadata, approve→anchor (real local chain), verify VERIFIED/MISMATCH/NOT_ANCHORED, amendment immutability, archival |
| API | httpx (async client against the real ASGI app) | Every endpoint × every role (authz matrix), security edge cases |
| Contract | Hardhat/Mocha | `anchor`, re-anchor revert, `onlyWriter`, `getAnchor`, owner-only `setWriter` |
| Frontend | Vitest + React Testing Library | Login form validation, upload dropzone validation, verify-result rendering (green/red) |

Deliberately **not** mocked: MongoDB, MinIO/R2, and (in `tests/integration/test_anchor.py`
and the workflow/verify integration tests) the blockchain itself — CI spins up a real
local Hardhat node and a real docker-compose Mongo/MinIO, and tests talk to real services
over the network rather than to mocks of them. This is a deliberate choice: the riskiest
parts of this system (the 3-way hash comparison, the anchor/confirm/promote sequence) are
exactly the parts a mock would be most likely to over-simplify.

## Current results (this codebase, as of Phase 12)

```
backend:    118 tests passed, 92.4% line coverage (gate: 60%)
contracts:  Hardhat test suite passing (anchor / re-anchor-reverts / onlyWriter / getAnchor / setWriter)
frontend:   Vitest suite passing (Login, FileDropzone, Verification result rendering)
```
Reproduce locally:
```bash
cd backend && pytest                 # coverage report printed, gate enforced via pyproject.toml
cd contracts && npx hardhat test
cd frontend && npm run test
```
`.github/workflows/ci.yml` runs all three jobs (`backend`, `contracts`, `frontend`) on every
PR and every push to `main`; a PR cannot merge unless all three are green (branch
protection is a manual GitHub repo setting — see `DEPLOYMENT.md`'s manual steps).

## Representative cases (Plan Part 20, mapped to actual test files)

| Case | Expected | Test |
|---|---|---|
| Valid login | 200 + tokens | `tests/api/test_auth.py` |
| Invalid password | 401, generic message | `tests/api/test_auth.py` |
| Tampered / `alg: none` JWT | 401 | `tests/unit/test_security.py` |
| Refresh-token reuse | session family revoked | `tests/api/test_auth.py` |
| Unauthorized role calls a permission-gated route | 403 `FORBIDDEN` | `tests/api/test_rbac.py`, `tests/api/test_authz_matrix.py` |
| Approver == uploader | 403 `MAKER_CHECKER_VIOLATION` | `tests/integration/test_workflow.py` |
| Point inside / outside / on-edge of a geofence | pass / 403 / deterministic | `tests/unit/test_geofence.py` |
| Low GPS accuracy / stale timestamp | 422 | `tests/unit/test_geofence.py` |
| Swapped lat/lng input | validation error | `tests/unit/test_geofence.py` |
| Valid upload | 201, hash + V1 DRAFT | `tests/integration/test_upload.py` |
| Oversized file | 413 | `tests/integration/test_upload.py` |
| MIME/magic-byte mismatch | 422 | `tests/integration/test_upload.py` |
| Malicious/path-traversal filename | stored under a server-generated key, not the client name | `tests/integration/test_upload.py` |
| Full DRAFT→…→ACTIVE happy path | anchored, version chain intact | `tests/integration/test_workflow.py` |
| Amendment V1→V2 | V2 anchored, V1 retained + marked SUPERSEDED, V1 bytes/hash untouched | `tests/integration/test_workflow.py` |
| Anchor tx failure/revert | document stays APPROVED(pending), app stays usable | `tests/integration/test_anchor.py`, `tests/integration/test_workflow.py` |
| Illegal transition (e.g. DRAFT→ACTIVE directly) | 409 `ILLEGAL_TRANSITION` | `tests/integration/test_workflow.py` |
| Untouched anchored version | VERIFIED | `tests/integration/test_verify.py` |
| Controlled 1-byte tamper post-anchor | MISMATCH, document flagged `TAMPERED` | `tests/integration/test_verify.py` |
| Stored-hash-in-Mongo tampered to match a tampered file | still MISMATCH vs. on-chain | `tests/integration/test_verify.py` |
| Never-anchored version | NOT_ANCHORED (not an error) | `tests/integration/test_verify.py` |
| Archive | hidden from default list, versions/anchors retained | `tests/integration/test_archival.py` |
| IDOR (another user's/role's document id) | 403/404 as appropriate | `tests/api/test_security_cases.py` |
| NoSQL-injection-shaped query payload | handled safely (typed filters, not string-built) | `tests/api/test_security_cases.py` |
| Audit log has no update/delete path | route/method not exposed | `tests/api/test_audit.py` |
| `/audit` called by a non-Auditor/Admin role | 403 | `tests/api/test_audit.py` |
| Reports aggregation on seeded data | correct counts | `tests/api/test_reports.py` |
| Global rate limiter | 429 past threshold; `/health` always exempt | `tests/api/test_hardening.py` |
| Security response headers present | `X-Frame-Options`, `Cache-Control: no-store`, etc. | `tests/api/test_hardening.py` |
| Contract: re-anchor same (doc, version) | reverts | `contracts/test/DocumentAnchor.test.ts` |
| Contract: non-writer calls `anchor` | reverts (`onlyWriter`) | `contracts/test/DocumentAnchor.test.ts` |
| Contract: non-owner calls `setWriter` | reverts | `contracts/test/DocumentAnchor.test.ts` |
| Frontend: verify result rendering | green VERIFIED / red MISMATCH | `frontend/src/pages/__tests__/Verification.test.tsx` |
| Frontend: upload dropzone validation | rejects disallowed file before submit | `frontend/src/components/__tests__/FileDropzone.test.tsx` |

## Not covered (explicitly, and why)

- **Load/performance testing** (locust/k6) — the plan lists this as light-touch and
  optional for a prototype (Part 22); not implemented. Latency targets in `SRS.md` §5 are
  design targets, not measured SLAs.
- **End-to-end browser automation** (Playwright) — listed as a Level-3/optional item (Plan
  Part 26); the golden-path and tamper-detect flows are instead exercised manually per
  `DEMO_SCRIPT.md` before every demo.
- **The optional background worker** (`app/workers/anchor_confirmer.py`) — excluded from
  the coverage gate (`pyproject.toml`'s `[tool.coverage.run] omit`); the synchronous
  confirm-on-approve path it duplicates is fully tested, and the plan's own cut-list names
  this component as safe to leave untested first if time runs short.
- **ClamAV / malware scanning** — not implemented (see `THREAT_MODEL.md` #7), so nothing to
  test.
