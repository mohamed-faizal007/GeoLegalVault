# Troubleshooting and re-running scenes (demo_video2)

## One-time setup (already done on this machine)
`demo_video/.venv` (Playwright + Chromium, reportlab, imageio-ffmpeg, pymongo, boto3) is reused; `ffmpeg` comes from `imageio-ffmpeg`.
Windows System.Speech (voice "Microsoft Zira Desktop", rate +1) makes the audio: `powershell -File demo_video2/tts.ps1`.

## Pipeline in one paragraph
`narration.py` is the single source of the spoken text (one sentence = one beat) and writes `audio/<scene>_<key>.txt`; `tts.ps1` makes one WAV per
sentence. Each `scenes/sceneNN_*.py` wraps every sentence's on-screen step in `with sc.beat(page, key, caption)`, which holds the picture at
least as long as the sentence and stamps the beat's start/end (and any trimmed wait) into the video as a tiny binary marker (bottom-right).
`assemble.py` decodes the markers, cuts every beat (long waits trimmed), places each sentence's audio at its beat, blanks the marker, builds the
SRT, both MP4s and `NARRATION_SCRIPT.md`. Recordings made before the marker existed (scenes 3-6) are aligned from the caption-bar changes.

## Symptoms
| Symptom | Cause / fix |
|---|---|
| `REFUSED: MONGODB_DB=...` | `scenes/common.py` aborts unless the database is `geolegalvault_demo`. Unset or correct the variable. |
| Approve is refused with `LOCATION_STALE` | The browser location reading is older than the server's freshness limit (120 s here) because a context sat idle. The harness now refreshes the location on every `geo=True` beat (`Scene.refresh_geo`). Nothing was approved or spent. |
| `STOP: V1/V2 is APPROVED but the anchor did not confirm` | The anchor did not confirm inside the request window. Do not start the worker and do not loop; report. (Never happened in the recorded run.) |
| Download from the viewer returns 403 not 404 | Zone check runs before the clearance check; a user with no assigned zone is refused at the zone step. Assign the zone first (scene 12b does, through `PATCH /users`). |
| `sync marker(s) ... not found` in `assemble.py` | A recording lost frames (heavy page such as Etherscan, or the headed window was resized/minimised). Run `python demo_video2/qa/check_markers.py` to see which beat; re-record only that scene if it is a read-only scene. Keep the browser window in front and do not touch it while recording. |
| Video canvas shrinks to a gray frame after some seconds | Headed window resized/minimised during recording (happened once, scene 15, which was re-recorded). |
| Etherscan beat blank | Network or the site's bot checks; the transaction hash is on the Anchor page. The page is loaded before the beat starts, so the beat itself is static. |
| Login lockout scene shows no "Attempt 1 of 5" | The counter (60 s window) was still active; wait a minute. Throwaway account only. |
| `/health` shows `chain: degraded` | The probe checks `CHAIN_RPC_URL` (a stub), not `SEPOLIA_RPC_URL`. Set `CHAIN_RPC_URL` from `SEPOLIA_RPC_URL` in the backend process (not in `.env`). Listed as a follow-up. |
| Pre-signed URL anywhere in a log | Must never happen: the harness replaces `window.open`, uses the URL once in memory, and re-raises errors without the URL. If you extend scene 12, keep that. |

## Re-running
- **Safe (read-only, only add audit/verification rows):** scenes 2, 5, 7, 8, 9, 12 (adds an ACCESS row), 14, 16, 17; slides 1 and 18.
- **Never again without a new fresh document:** 3 (creates the throwaway user), 4 (uploads), 6 and 11b (real Sepolia transactions), 10 (tamper; restores), 11, 13 (archive, irreversible in the app), 12b (assigns the zone), 15 (throwaway lockout, wait 60 s between runs).
- Re-assemble any time from the existing recordings: `demo_video/.venv/Scripts/python.exe demo_video2/assemble.py`.
- QA helpers: `qa/check_markers.py`, `qa/frames.py video t...`, `qa/sheet.py out cols t...`.

## Restoring the tampered object (if scene 10 is ever interrupted)
The original V1 bytes are in `demo_video2/work/original_v1.bin` (gitignored); write them back to the same key `docs/<documentId>/v1-<sha256>` (this document's own object) and check that their SHA-256 equals `document_versions.sha256`. The script does this in a `finally` block.
