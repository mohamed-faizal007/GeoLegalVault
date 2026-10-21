# Troubleshooting and re-running scenes

## One-time setup (already done on this machine)
```
python -m venv demo_video/.venv
demo_video/.venv/Scripts/python.exe -m pip install playwright reportlab imageio-ffmpeg pymongo boto3 pypdf
demo_video/.venv/Scripts/python.exe -m playwright install chromium
```
`ffmpeg` is not on PATH; `assemble.py` uses the binary from `imageio-ffmpeg`.

## Before any recording: port 8000 and 5173 must hold ONLY GeoLegalVault
```
Get-NetTCPConnection -State Listen -LocalPort 8000,5173 | Select LocalPort,OwningProcess
Get-CimInstance Win32_Process -Filter "ProcessId=<pid>" | Select CommandLine
```
Another project's server on 8000 gives wrong answers (this happened: a `Government_Scheme-AI` uvicorn). Stop it yourself; do not kill unknown processes blindly. Also stop stale `proofchain-*` or `geolegalvault-backend` containers (`docker ps`).

## Start the stack (no anchor worker!)
```
docker compose up -d mongo storage storage-init            # NOT a bare "up -d": that also starts backend + worker
cd backend ; $env:ANCHOR_CONFIRM_POLL_ATTEMPTS=90 ; $env:ANCHOR_CONFIRM_POLL_INTERVAL_SEC=1.0
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
cd frontend ; npm run dev -- --port 5173 --strictPort
Invoke-RestMethod http://localhost:8000/api/v1/health      # status ok; chain "degraded" is expected (placeholder CHAIN_RPC_URL); anchor_worker "stale" is expected
```
The two `ANCHOR_CONFIRM_*` variables make the approve request wait for the Sepolia block (about 12 s). Without them the document stays APPROVED until the optional worker runs. Never run `docker compose down -v`, volume prune or system prune; never start the anchor worker against the dev DB.

## Geofence limits on this machine
`.env` has `GEO_ACCURACY_MAX_M=300` and `GEO_FRESHNESS_MAX_SEC=120` (code defaults: 100 and 60). **They were not changed and must not be "restored to 100"** unless you decide to. The poor-accuracy scene uses 500 m, which fails under either value. `LOCATION_LOW_CONFIDENCE` on a good reading usually means the wrong backend is on port 8000.

## Re-running one scene
Run from `demo_video/scenes` with the demo venv: `..\.venv\Scripts\python.exe sceneNN_name.py`. Output: `demo_video/recordings/<scene>/<role>.webm` + `timeline.json`. Shared ids are in `demo_video/state.json` (gitignored; contains the throwaway user's password).

| Scene file | Safe to re-run? | Notes |
|---|---|---|
| scene02_login_roles, scene03b_lockout (throwaway only), scene05_geofence_denied, scene07_anchor, scene08_clearance, scene09_verify_ok, scene11_not_anchored, scene12_mongo_audit, scene04b_hash_storage, scene06a2_selfapprove_api | Yes | Read-only apart from audit/verification rows. Scene 3b needs a 1-minute wait before the throwaway account can log in again. |
| scene10_tamper | Yes | Changes one byte of the stored object, then restores the original (from `samples/DEMO_Lease_Agreement_v1.pdf`, hash-checked). It restores even if it fails midway. |
| scene03_admin | No | Creates the user; a second run fails with 409. Delete or rename first. |
| scene04_upload, scene06a_maker_checker | No | Create new documents. A second run adds duplicates (change the title). |
| scene06b_approve | **No** | Sends a real Sepolia transaction. The script refuses to run twice (`approved_at` in state.json). |

Rebuild the video after changing recordings or `assemble.py` / `narration.py`:
```
demo_video\.venv\Scripts\python.exe demo_video\narration.py                 # writes NARRATION_SCRIPT.md
# write audio\sXX.txt from narration.SCENES, then:
powershell -File demo_video\tts.ps1 -Rate 0                                # one WAV per scene (Zira)
demo_video\.venv\Scripts\python.exe demo_video\assemble.py                 # mp4s, captions.srt, timestamps
```
`assemble.py` PLAN has the cut points per scene (timeline seconds). Timeline seconds are from the start of the scene script, and the per-file offsets are estimates; check frames after changing cuts.

## Common problems
- **Login fails / 5 failures:** one-minute lockout per account. Never try more than twice on a real account.
- **Create-user 409:** email exists.
- **Spinner for ~15 s on a hidden document (scene 8):** the UI retries the 404 before showing the message.
- **Document stays APPROVED:** the transaction was not confirmed within the request window; start the backend with the two variables above or run the worker deliberately (it can re-send old stuck rows: run `python -m app.workers.anchor_confirmer --dry-run` first).
- **Etherscan page blank:** the explorer's bot checks; the hash is on the Anchor Record page.
- **Wallet balance:** `backend\.venv\Scripts\python.exe scripts\faucet_check.py` (prints address and balance only).
- **Secrets:** never print `.env` values; `demo_video/scenes/common.py` reads them without echoing.
