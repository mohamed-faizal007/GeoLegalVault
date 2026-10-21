# Features demonstrated - GeoLegalVault demo (recorded 2026-10-21)

Everything marked Done was recorded from the real running frontend and backend. Nothing was mocked. "Supplementary view" = real
read-only output (MongoDB, storage listing, raw API call) in a clearly labelled, non-UI page.

## Done
| # | Scene | What was shown | Evidence |
|---|---|---|---|
| 1 | Problem and idea | Slides | - |
| 2 | Login, roles, clearance | Three real logins in separate browser contexts; different menus per role | UI |
| 3 | Admin | Geofence zone list; create a throwaway user (AUDITOR, clearance PUBLIC, password masked) | UI |
| 3b | Login lockout | 6 wrong passwords on the throwaway account only -> "Too many attempts" | UI |
| 4 | Upload inside the zone | Upload form, DRAFT, SHA-256 (Version History, shortened), submit -> SUBMITTED | UI + supplementary (MongoDB rows, bucket HEAD/listing) |
| 5 | Upload refused | Outside the zone -> `GEOFENCE_DENIED` (403); accuracy 500 m -> `LOCATION_LOW_CONFIDENCE` (422) | UI + supplementary (audit row) |
| 6 | Review, maker-checker, approval | Reviewing Officer passes both documents; uploader's own approve -> `MAKER_CHECKER_VIOLATION` (403); a different Legal Officer approves inside the zone; status ACTIVE | UI + supplementary (raw API call) |
| 7 | Anchor on Sepolia | Anchor record, live on-chain read, public Etherscan page (Status Success, Sepolia Testnet) | UI + Etherscan |
| 8 | Clearance | PUBLIC user: lease not listed; direct link -> "couldn't be found" (HTTP_404); API returns identical 404 for real and made-up ids | UI + supplementary |
| 9 | Verify genuine file | VERIFIED, three equal hashes | UI |
| 10 | Tamper | `demo/tamper.py` changes one byte of the stored object; MISMATCH; original bytes restored; VERIFIED again | UI + supplementary (terminal output) |
| 11 | Other outcomes | NOT_ANCHORED live on Doc B; the other three on a slide | UI + slide |
| 12 | Audit and data | Audit Logs page; audit rows for the lease; collections and id links; bucket and anchor record | UI + supplementary |
| 13 | Summary and future work | Slides | - |

## Partly shown
| Item | What is missing and why |
|---|---|
| Self-approval block | The UI hides the Approve button for the uploader, so the 403 can only be shown by a direct API call (labelled as such). |
| SHA-256 in the UI | Document Details does not show the hash in this build; only Version History (shortened) and the Verification page (full). The full value is in the supplementary view. |
| ANCHOR_MISSING, FILE_MISSING, CHAIN_UNREACHABLE | Explained on a slide, not triggered: each would need deleting a stored object, editing an anchor row or breaking the RPC in the shared dev setup. |
| Geofence polygon editing | The zone list is shown; no zone was created or edited. |
| Location | Supplied by the Playwright test harness (labelled on screen); the server validated it each time. A real device would use browser GPS / Wi-Fi location. |
| Anchoring wait | The approve request waits for the Sepolia block. The backend process was started with `ANCHOR_CONFIRM_POLL_ATTEMPTS=90`, `ANCHOR_CONFIRM_POLL_INTERVAL_SEC=1.0` (process environment only; `.env` and code unchanged) so the document reached ACTIVE without the anchor worker. With the default 1.5 s window it would have stayed APPROVED until a worker ran. |

## Not demonstrated
- **Amendment / version 2** (skipped by choice; would cost a second transaction): Request amendment, Upload amended version, SUPERSEDED, `prev_version_hash`.
- **The optional anchor worker** and the admin "Retry anchoring" re-queue (never started against the dev database, by instruction). Note the Dashboard shows an alert for two old stuck documents from earlier dev work.
- Download via pre-signed URL, archive, reports page, System Health tab (its "chain: degraded" reflects a placeholder `CHAIN_RPC_URL`, not the Sepolia connection used for anchoring).
- Clearing the integrity flag.
- Stale-location rejection (`LOCATION_STALE`), invalid location (`INVALID_LOCATION`).
- Anything about a hash-chained audit log (not implemented: CMP-01), Merkle trees (none: one SHA-256 per file), per-user wallets (none: one backend service wallet).

## State the demo left behind (for your clean-up)
All names start with `DEMO-20261021-` or `demo-viewer-20261021`.
- **Users:** `demo-viewer-20261021@geolegalvault.demo` (AUDITOR, PUBLIC). Its throwaway password is only in `demo_video/state.json` (gitignored).
- **Documents:** `DEMO-20261021-Lease Agreement` (ACTIVE, **integrity_flag = TAMPERED**), `DEMO-20261021-Doc B maker-checker` (PENDING_APPROVAL, never approved). One `blockchain_anchors` row and **one Sepolia transaction** `0x91d0a874278c482b27c1d4929ef50208cc1d50e73fbf49a6bf384109f00bcb2f` (block 11963160, contract `0xA277982716770CD77eb509109D1D1A1d2CBb63fb`).
- **Storage objects** in `geolegalvault-dev`: `docs/<leaseId>/v1-31924e84...` and the Doc B object (same bytes, different document id). The lease object was changed by one byte and **restored to the original bytes** (checked by hash).
- **Rows added:** `verification_records` (lease: VERIFIED, MISMATCH, VERIFIED, plus one NOT_ANCHORED for Doc B), `audit_logs` (logins, GEOFENCE_DENIED, UPLOAD, SUBMIT, REVIEW_*, APPROVE, ANCHOR_OK, ACTIVATE, ACCESS_DENIED, VERIFY_*, USER_CREATE, LOGIN_FAILURE), `refresh_sessions`, `login_rate_limits` (the lockout counter).
- **Test ETH:** balance before `0.047359968198771912`, after `0.047359968194149763`. Spent `0.000000000004622149 ETH` (matches the Etherscan fee). Test ETH has no value.
- **TAMPERED flag:** left set. Clearing it (Administrator only) re-runs the three checks first, so it would now succeed. The Administrator's clearance (INTERNAL) is below this CONFIDENTIAL document, which the server treats as not found, so another administrator must first raise `administrator@geolegalvault.demo` to at least CONFIDENTIAL in Admin Panel > Users > Edit (nobody can change their own clearance). From the code; not run.
- **Processes I started and left running:** backend (port 8000, with the two `ANCHOR_CONFIRM_*` variables), Vite (port 5173), Docker `geolegalvault-mongo-1`, `geolegalvault-storage-1`. The compose `mongo` container was recreated at the start (same data volume).
- **Not changed:** `.env`, application code, `GEO_ACCURACY_MAX_M`. This machine uses **300 m and 120 s** (code defaults are 100 m and 60 s).
