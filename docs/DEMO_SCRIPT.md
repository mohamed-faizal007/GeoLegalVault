# Demo Script — 10 minutes

Run this exact sequence (Plan Part 34) against the deployed stack (or `docker-compose up`
locally with a real Sepolia contract configured — the anchoring steps need a real chain).
Seed the demo data first: `python scripts/seed.py --demo && python scripts/seed.py
--seed-documents` (see `DEPLOYMENT.md` step 4). Demo credentials (all password
`Demo@Pass123!`): `legal_officer@geolegalvault.demo`, `reviewing_officer@…`,
`authorized_staff@…`, `auditor@…`, `administrator@…`.

Rehearse this twice before presenting it live — the DoD requires it to run end-to-end
twice with no manual database fixes.

| Min | Step | On screen |
|---|---|---|
| 0:00 | Log in as `legal_officer@geolegalvault.demo` on the **Login** page. | Dashboard loads with a visible **role badge** ("Legal Officer") and the sidebar shows exactly the pages that role can use. |
| 0:45 | Open **Geofence Status**. | Browser prompts for location; use a real or DevTools-overridden coordinate inside the seeded "HQ Campus (demo)" polygon (`scripts/seed.py` prints the exact inside point). Page shows a green "Inside" badge with the coordinates and reported accuracy. |
| 1:30 | Go to **Upload**, pick a small PDF/text file, fill in title/type/classification, submit. | Progress indicator → 201 response → the new document appears in the **Document Repository** with its **SHA-256 shown** on the Document Details page. |
| 2:30 | Switch to the R2 (or MinIO) console. | Show the object under `docs/{document_id}/v1` — a private bucket, a server-generated key (not the original filename), encrypted at rest. |
| 3:15 | Switch to the Atlas (or `mongosh`) console. | Show the `documents` and `document_versions` documents for this upload — the `sha256` field matches what the UI showed. |
| 4:00 | Back in the app: **Submit** → log in as `reviewing_officer@…` and **Review → Approve** → log in as `legal_officer@…` and **Approve**. | Status badge moves DRAFT → SUBMITTED → UNDER_REVIEW → PENDING_APPROVAL → APPROVED; approving is the one click that (invisibly, automatically) triggers anchoring — there is no separate "anchor" button anywhere in the UI. |
| 5:00 | Open **Blockchain Verification** for this version. | `blockchain_anchors` status goes PENDING → CONFIRMED; click the **Etherscan link** and show the real transaction on Sepolia (`https://sepolia.etherscan.io/tx/…`) with the anchored hash visible in the tx input data. |
| 6:00 | On the now-ACTIVE document, click **Amend** (reason: e.g. "correcting clause wording"), then upload a corrected file as V2. Run it through Submit → Review → Approve again. | **Version History** shows V1 marked **SUPERSEDED** and V2 **ACTIVE**, both independently anchored with their own Etherscan links. |
| 7:00 | Switch to the R2/MinIO console and **overwrite** V2's object directly (upload replacement bytes to the same key) — an action only possible with direct storage access, not through the app. | Console shows the object was modified outside the application. |
| 7:45 | Back in the app, open **Verification** for V2 and click **Verify**. | Big **red "MISMATCH — tamper detected"** banner; the 3-way hash row shows recomputed ≠ stored/on-chain; the document's integrity flag is now set. |
| 8:30 | Open **Verification** for V1 (never touched). | Big **green "VERIFIED"** banner — the unchanged version still passes, proving the mismatch above is specific to the tampered bytes, not a broken check. |
| 9:00 | Open **Audit Logs** (as `auditor@…` or `administrator@…`). | Filter to this document: see `UPLOAD`, `SUBMIT`, `REVIEW_*`, `APPROVE`, `ANCHOR_OK` (×2), `AMEND_REQ`, `VERIFY_FAIL`, `VERIFY_PASS`, and the earlier `GEOFENCE_DENIED`/location events, each with actor, result, and timestamp. |
| 9:30 | Attempt a sensitive action (e.g. Upload) from a location outside the geofence (DevTools sensor override, or a phone off-site). | Clear **403 "outside authorized location"** message on screen — not a silent failure, and not a client-side check the user could bypass by editing the page (say this explicitly: the server independently re-ran the location check). |
| 10:00 | Close on one slide: **honest limitations.** | *"Tamper-evident, not tamper-proof — an on-chain hash proves a file hasn't changed since anchoring, it doesn't prevent access to begin with. Geofencing is a policy control, not a cryptographic guarantee — browser GPS is spoofable, and this prototype does not attempt hardware attestation."* |

## If something goes wrong live

- **Anchor stuck PENDING past a minute or two:** this is expected sometimes on a public
  testnet under load — the document stays usable (status APPROVED, pending anchor) exactly
  as designed. Narrate this as the intended failure-handling behavior, not a bug, and move
  on; check back on it later in the demo, or re-run `python scripts/seed.py
  --seed-documents` beforehand so several already-anchored documents exist as a fallback.
- **RPC rate-limited:** switch narration to one of the pre-seeded, already-anchored/
  tampered documents from `--seed-documents` instead of live-anchoring a fresh one.
- **Geofence override not taking effect:** confirm the browser tab actually has location
  permission granted and DevTools' sensor override is active on the correct tab (a common
  demo hiccup, not an app bug).
