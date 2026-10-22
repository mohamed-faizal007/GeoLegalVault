# Features demonstrated: GeoLegalVault demo v2

Video: `GeoLegalVault_Demo_v2.mp4` (voice + soft subtitles), `GeoLegalVault_Demo_v2_silent_captions.mp4` (captions burned in), 20:28, 1080p H.264.
Everything on screen was recorded from the real running stack (Playwright + Chromium, headed, 1920x1080), except the clearly
labelled **Supplementary view** pages (real read-only output of MongoDB, the bucket, the API or a script, with secrets removed) and the
slides. Browser location is supplied by the test harness (labelled on screen); the server still validates it.

- **Database:** `geolegalvault_demo` (21 seeded documents at the start; the dev database `geolegalvault` was never touched).
- **Backend / frontend:** `http://localhost:8001` / `http://localhost:5174`. The anchor worker was **not** started.
- **Chain:** Ethereum **Sepolia testnet** (chain id 11155111), one service wallet, contract `DocumentAnchor`.
- **The fresh document:** `DEMO-20261022-Lease`, INTERNAL, document id `6ad96b509f623b34b6ae671b`, uploaded by Authorized Staff.

## Sepolia transactions (the two that were approved)
| | version | tx hash | block |
|---|---|---|---|
| 1 | V1 | `0x1bbbae29ee7a0225e42f7d3383f2d938312c354fd8980bd5708b6753a42e47cc` | 11966398 |
| 2 | V2 | `0x5e83858459b6302651bdd29523d16b11d570a519b908a9e2b9b7885c36744792` | 11966608 |

Service wallet `0xa1C45A09A55586c5f99C2Fe53307AD3881c25837` (address only): balance before **0.047359968169822663 ETH**, after V1
0.047359967850164569, after V2 **0.047359967530019933** (about 6.4e-10 ETH in total). No other transaction was sent.

## Done (shown live, in the real UI unless marked)
| # | Scene (time) | What |
|---|---|---|
| 1 | Intro (0:04) | problem and idea, two slides |
| 2 | Login, roles, clearance, names (1:16) | three separate browser sessions; names in the welcome line; counts differ by clearance; "21 documents, 2 archived" |
| 3 | Admin (2:26) | Geofences tab, Users tab with names/roles/clearance, throwaway PUBLIC user created (masked password) |
| 4 | Upload V1 (3:21) | inside the zone, DRAFT, supplementary views of the document/version rows (SHA-256 highlighted) and the private bucket key, submit, Version History |
| 5 | Refused uploads (4:47) | GEOFENCE_DENIED (outside); LOCATION_LOW_CONFIDENCE (500 m); audit row for the first only (spoken: the second goes to the application log); Geofence Status policy note |
| 6 | Maker-checker and approval (5:53) | seeded self-approval attempt refused with MAKER_CHECKER_VIOLATION (supplementary API view, nothing changed); Reviewing Officer reviews; a different Legal Officer approves; **tx 1** |
| 7 | Anchoring (7:15) | Anchor page: recorded vs live on-chain hash side by side, Match, "Sepolia testnet", Copy button; contract fields; Etherscan Status Success + fee (dimmed, rows highlighted) |
| 8 | Clearance 404 (8:29) | PUBLIC viewer on the INTERNAL lease (not listed, 404, identical to a made-up id); Administrator on a seeded CONFIDENTIAL document (404); ACCESS_DENIED audit rows |
| 9 | Verify VERIFIED (9:33) | three-way hash comparison |
| 10 | Tamper (10:06) | original bytes saved locally, `demo/tamper.py` (with `MONGODB_DB=geolegalvault_demo`) changes one byte of this document's own object, MISMATCH, TAMPERED flag, restore with hash == recorded SHA-256, VERIFIED, flag still set, **Administrator clears it** ("Clear integrity flag", 10+ character reason) |
| 11 | **Amendment V2** (11:34) | request amendment (geofenced), V2 upload by Authorized Staff, submit, review, approval by a different person, **tx 2**; Version History (V2 ACTIVE+CONFIRMED, V1 grey SUPERSEDED, no "current" label); full `prev_version_hash` = V1 SHA-256 (supplementary view; no `parent_version_id`); V2 anchor page Match; V2 and V1 both VERIFIED, Verification page never says "superseded" |
| 12 | **Download** (13:48) | current version only, geofenced; downloaded bytes hash == recorded SHA-256 (the pre-signed URL is never displayed); ACCESS audit row with the version id; GEOFENCE_DENIED outside the zone; 404 for the below-clearance viewer (inside an assigned zone) |
| 13 | **Archive** (14:44) | Legal Officer archives the fresh document; gone from default Dashboard/Repository, present under Archived; no undo in the backend (said) |
| 14 | Other outcomes (15:27) | NOT_ANCHORED live on a seeded draft; one slide for all six outcomes, held for the whole list; ANCHOR_MISSING / FILE_MISSING / CHAIN_UNREACHABLE labelled "not triggered live" |
| 15 | Login protection (16:23) | Attempt 1 of 5 ... 5 of 5, the pause message, then "Too many attempts" (throwaway account only); `login_rate_limits` view |
| 16 | Audit and data (16:59) | Audit Logs at the top; action dropdown, actor search, document filter, "View audit trail" from the document page; collections, id links, bucket (supplementary views) |
| 17 | Reports (18:34) | Auditor's Reports tab; 22 accessible / 3 archived / 19 shown; ends on the outlined Mismatches card and ARCHIVED bar |
| 18 | Summary (19:05) | components, honest limits, future work, ONE slide for the planned next version with no design details |

## Partial
- **Audit document filter (scene 16):** the filter's dropdown cannot find an archived document, so it is demonstrated on a seeded active document; the lease's trail is reached with "View audit trail". See discrepancies.
- **`login_rate_limits` view (scene 15):** shows `count` and `expires_at` but not the row key (the email), so it does not say whose row it is. The label says "throwaway account only".
- **Scene 5 audit view:** the meta column is cut off after the location (`{"accuracy_m"...`). Cosmetic.
- **Scenes 3-6** were recorded before the exact per-beat sync marker existed; they are aligned by snapping each beat to the caption-bar change in the video (checked: shifts within 0.05 s, one scene 1.5 s corrected by the snap). Scenes 2 and 7-18 use exact markers.

## Not shown, and why
- **Anchor worker / re-queue of stuck anchors:** the worker is opt-in and must not be started for this recording; no anchor was stuck.
- **ANCHOR_MISSING, FILE_MISSING, CHAIN_UNREACHABLE live:** would require damaging the shared dev setup; shown on a slide only.
- **Changes requested by the reviewer (loop back to the uploader):** mentioned in narration, not filmed.
- **User deactivation, geofence creation/edit, Settings, System Health tab:** not part of the storyline.
- **Mainnet, Merkle trees, NLP, per-user wallets:** out of scope (Guardrails #3, #8).

## What the demo created / changed in `geolegalvault_demo`
- 1 document (2 versions, 2 CONFIRMED anchors, final status ARCHIVED); objects `docs/6ad96b509f623b34b6ae671b/v1-...` and `v2-...` in the shared bucket (the V1 object was tampered and restored byte-for-byte).
- 1 throwaway user `demo-viewer-20261022@geolegalvault.demo` (role AUDITOR, clearance PUBLIC; the HQ zone was assigned through the real `PATCH /users` API in scene 12 so the clearance check is reachable).
- Audit rows (logins, upload, review, approvals, ACCESS, ACCESS_DENIED, GEOFENCE_DENIED, INTEGRITY_CLEARED, ARCHIVE...), verification_records (V1, V2, and one NOT_ANCHORED record on the seeded draft "Public Notice - Change of Registered Office").
- One refused self-approval attempt on the seeded "Shareholder Agreement Amendment - Series B Terms" (403 before anything changed; still PENDING_APPROVAL).
- Local, gitignored: `demo_video2/work/original_v1.bin`, recordings, audio, build, state.

## Run notes (honest account)
- **LOCATION_STALE incident (scene 11):** the first approval attempt for V2 was refused with `LOCATION_STALE` (the Legal Officer's browser location had been set minutes earlier; the server refuses readings older than the freshness limit). It was refused before approving (no APPROVE audit row, no anchor, no gas). The harness now refreshes the location before geofenced beats, and the approval was re-done once in `scene11b_approve_v2.py`, after checking V2 was still PENDING_APPROVAL with no anchor. The anchor itself confirmed at once.
- **Scene 15** was recorded twice: the first video went corrupt after ~30 s (the browser canvas shrank), so it was re-recorded; throwaway account only.
- **Scene 12** was split: the 404 beat is `scene12b_clearance_404.py` because the first attempt returned 403 (see "Download order of checks").

## Discrepancies found
1. **Health probe checks the wrong chain URL.** `/api/v1/health` probes `CHAIN_RPC_URL` (`backend/app/main.py:79`), not `SEPOLIA_RPC_URL` that anchoring uses, so `chain` shows `degraded` even when Sepolia is healthy (this run used a process-level `CHAIN_RPC_URL` override to get `reachable`). **Follow-up:** make the probe check the Sepolia chain id and the contract code, with tests.
2. **`hardhat-node` compose service is a placeholder** that runs no node (`tail -f /dev/null`), kept only so the stub URL answers. **Follow-up:** fix or remove the stub.
3. **`docs/API.md:52`** says archive accepts `ACTIVE/SUPERSEDED`; the code accepts `ACTIVE` only (a document is never SUPERSEDED; only version rows are). Not edited.
4. **`CHAIN_RPC_URL` masking note:** besides the health probe, `backend/app/services/anchor_errors.py:112` reads `CHAIN_RPC_URL` (and `SEPOLIA_RPC_URL`) only to mask RPC URLs in anchor-failure logs; `docker-compose.yml` sets it for the backend and worker. Nothing else sends traffic to it.
5. **Audit page document filter** searches only non-archived documents (it uses the default list), so an archived document cannot be selected there.
6. **A 404 on a document page is retried by the UI**, so one visit wrote several `ACCESS_DENIED` rows (four for one Administrator visit in scene 8).
7. **Download enforcement order:** the zone check runs before the clearance check, so a PUBLIC user with no assigned zone gets 403 `GEOFENCE_DENIED` for a download, not 404 (by design per Guardrail #5; the 404 needs a zone-assigned user).
8. **Document Details layout:** the owner's id text overlaps the Created column at 1920x1080 (cosmetic).
9. **Geofences tab** lists a zone's name and vertex count only; the polygon coordinates are not shown for an existing zone.
