# Re-record checklist: the 14 review items and the 3 new features

Timestamps are in `GeoLegalVault_Demo_v2.mp4` (m:ss). Status: **fixed**, **partly**, **not fixed**.

| # | Item from the review of the first video | Status | Where / how |
|---|---|---|---|
| 1 | No stuck-anchor banner or leftover dev documents | **fixed** | whole video runs on `geolegalvault_demo`; dashboards at 1:28 and 15:01 show no banner |
| 2 | Counts consistent; archived gap explained | **fixed** | 1:39 "21 documents, two archived"; 15:01 Dashboard back to 19 after the archive; 18:44 Reports note "22 ... including 3 archived ... 19" |
| 3 | Narration synced per sentence, checked over the whole video | **fixed** (see note) | one WAV per sentence; each beat held at least as long as its sentence; scenes 2, 7-18 cut from exact sync markers decoded from the video; scenes 3-6 (recorded before the markers) snapped to the caption-bar changes (shifts <= 0.05 s, one scene 1.5 s corrected) |
| 4 | Supplementary views readable, cropped, key field highlighted, labelled | **fixed** | 22-28 px at 1080p; highlights: sha256 (4:02, 4:17), GEOFENCE_DENIED (5:23), MAKER_CHECKER_VIOLATION (6:10), 404 (8:49), ACCESS_DENIED (9:21), ACCESS row + version id (14:19), download hash MATCH (14:09). Nit: scene 5 audit view has a cut-off meta fragment |
| 5 | Names instead of raw ids | **fixed** | welcome line 1:28; owner name on every document page; Audit Logs actor/target names with ids as secondary text (16:59-17:41) |
| 6 | Audit Logs at the top; action dropdown, actor search, document filter, "View audit trail" | **fixed** (with a limit) | 16:59-17:41, held 8 s+ on the filtered trail. The document filter cannot find archived documents, so it is shown on a seeded document (see FEATURES_DEMONSTRATED discrepancy 5) |
| 7 | Anchor page: both hashes, Match, Sepolia testnet label, Copy button in one view, V1 and V2 | **fixed** | V1 7:24-7:40, V2 13:28 |
| 8 | Etherscan zoom to Status: Success and the fee, bright page dimmed | **fixed** | 8:10 (Status and Transaction Fee outlined, overlay dim) |
| 9 | Lockout: Attempt 1 of 5 through 5 and the lockout message | **fixed** | 16:29-16:45 (then "Too many attempts") |
| 10 | Six-outcomes slide held for the whole narration of the list | **fixed** | 15:43-16:29, one slide for all five sentences |
| 11 | `login_rate_limits` counters as a labelled supplementary view | **partly** | 16:52 shows `count` and `expires_at`; the row key (the email) is not shown. Fix = re-record scene 15 showing `_id` |
| 12 | Spoken sentence: zone denial audited, LOCATION_LOW_CONFIDENCE goes to the application log | **fixed** | 5:23 |
| 13 | Cursor highlight smaller, shorter dwell, hidden over button labels | **fixed** | 20 px ring, fades after 0.6 s, hidden over buttons/links/inputs (checked on frames, not frame by frame) |
| 14 | Slide wording rules | **fixed** | "tamper-evident", "policy-level geofencing", Sepolia TESTNET; no "guaranteed", "mainnet", "tamper-proof"; the app has no rejected state ("changes requested") |

| New feature | Status | Where |
|---|---|---|
| Amendment V2 (request, upload, review, approval, tx 2, Version History, hash link, verify V2 and V1) | **fixed** | 11:34-13:48 |
| Download (current version, geofenced, hash match without showing the URL, ACCESS audit, denials) | **fixed** | 13:48-14:44 |
| Archive (Legal Officer, disappears from default views, Archived filter, no undo) | **fixed** | 14:44-15:27 |

## If you want to improve something later (no live data is consumed by these)
- Scene 15 only: add the row key to the `login_rate_limits` view (throwaway account; wait about a minute between runs, the counter expires).
- Scene 5 only: crop the audit meta to `location=...` (read-only scene; adds one more GEOFENCE_DENIED row).
- Scenes 3, 4, 6, 10, 11, 13 create or change data (user, document, approvals, tamper, archive): **do not re-run** without a fresh document and fresh approvals (each approval is a real Sepolia transaction).
