# Recording checklist (re-recording or recording your own voice)

## Before
- [ ] Ports 8000 and 5173 hold only GeoLegalVault (see TROUBLESHOOTING.md). One backend only.
- [ ] `docker ps`: `geolegalvault-mongo-1` and `geolegalvault-storage-1` healthy; no worker container.
- [ ] `/api/v1/health`: status ok (chain "degraded" and anchor_worker "stale" are expected).
- [ ] Backend started with `ANCHOR_CONFIRM_POLL_ATTEMPTS=90` and `ANCHOR_CONFIRM_POLL_INTERVAL_SEC=1.0`.
- [ ] Wallet has test ETH: `scripts\faucet_check.py` (about 0.047 ETH before this demo; an approval costs about 5e-12 ETH).
- [ ] Demo users seeded (`scripts/seed.py --demo`, safe to repeat). Password is in `scripts/seed.py`; never show it.
- [ ] Do not use the old documents (Manual Verify NDA, Test Contract, Lifecycle Test, Approval Demo, Anchor Demo): their stored files are missing.
- [ ] New documents use the prefix `DEMO-<date>-`.
- [ ] Window 1920x1080, headed Chromium, `slow_mo` 400 ms (the scripts do this).

## During
- [ ] Say "Ethereum Sepolia testnet". Say tamper-evident (detects), not prevents. Say policy-level geofencing, prototype.
- [ ] The on-screen label "Browser location supplied by test harness - the server still validates it" must be visible whenever location matters.
- [ ] Supplementary views are labelled; say aloud that they are not the app UI.
- [ ] No `.env` values, passwords, JWT secret, wallet key, RPC URL or storage keys on screen. (The throwaway password field is masked; the wallet address and contract address are public.)
- [ ] Scene 6b sends a real transaction: one time only.

## After
- [ ] `git status`: only `demo_video/` and `.gitignore` are new/modified by the demo (plus your own untracked `demo/`, `DEMO_RUNBOOK.md`, `docs/PROJECT_EXPLAINED.md`).
- [ ] `.env` unchanged; `GEO_ACCURACY_MAX_M` is still 300 here.
- [ ] Review the clean-up list in FEATURES_DEMONSTRATED.md.

## To record your own voice
Play `GeoLegalVault_Demo_silent_captions.mp4` (captions burned in) and read `NARRATION_SCRIPT.md` (the "Say" text is exactly what the synthetic voice read; timestamps per scene are listed). Record audio separately and mux it with ffmpeg, or use any editor.

## QA done on this build
Frames at every scene boundary were extracted and inspected: captions readable and clear of the app's caption bar, nothing cut off, no secrets visible. Known weakness: the supplementary views use small monospace text (16 px at 1080p); the narration reads out what matters. Narration is synchronised per scene, not per sentence, so a sentence can lead or trail its screen by a few seconds.
