# Recording checklist (recording your own voice, or a new take)

## Your own voice over the finished video
1. Open `GeoLegalVault_Demo_v2_silent_captions.mp4` (no audio, captions burned in, one caption per spoken sentence).
2. Read the text in `NARRATION_SCRIPT.md` (each sentence has its timestamp); captions are timed to the same sentences.
3. Always say: Ethereum **Sepolia testnet**, tamper-**evident**, policy-level geofencing, prototype. Never say the system prevents tampering, promises a location, or runs on mainnet. The app has no rejected state: say "changes requested".

## Before any new recording (nothing is re-run automatically)
- [ ] Ports: 8001 = demo backend, 5174 = frontend, nothing else on them (`netstat -ano | findstr ":8001 :5174"`). Do not kill anything you do not recognise.
- [ ] Containers: only `geolegalvault-mongo-1` and `geolegalvault-storage-1` are needed. Never start the backend/worker containers; never `down -v`, volume prune or system prune.
- [ ] Backend started with **process-level** env only: `MONGODB_DB=geolegalvault_demo`, `CORS_ORIGINS` for `http://localhost:5174`, `ANCHOR_CONFIRM_POLL_ATTEMPTS=90`, `ANCHOR_CONFIRM_POLL_INTERVAL_SEC=1.0`, and `CHAIN_RPC_URL` set from `SEPOLIA_RPC_URL` (so `/health` shows chain `reachable`). No `.env` or code edits.
- [ ] Frontend: `VITE_API_BASE_URL=http://localhost:8001/api/v1`, `--port 5174 --strictPort`. Use `http://localhost:5174` (not 127.0.0.1).
- [ ] Probe that the backend writes to the demo DB: `MONGODB_DB=geolegalvault_demo backend/.venv/Scripts/python.exe demo/seed_realistic.py --report` (demo audit +1, dev audit +0; 21 seeded documents; empty stuck-anchor list).
- [ ] The anchor worker is **not** running (`/health` shows `anchor_worker: stale`; that is expected).
- [ ] Wallet has test ETH (`PYTHONPATH=backend backend/.venv/Scripts/python.exe demo_video2/wallet_balance.py` prints the address and balance only).
- [ ] No secrets on screen: no `.env` values, passwords, tokens, keys, RPC URLs with keys, storage keys or pre-signed URLs.

## A full new take needs a NEW fresh document
Each approval is a real Sepolia testnet transaction (two per take: V1 and V2). Scenes 3, 4, 6, 10, 11, 13 create or change data and are
not idempotent (see `RERECORD_CHECKLIST.md` and `TROUBLESHOOTING.md`). Use a new date constant in `scenes/common.py` (`DATE`) for a new take.

## Order of scripts (venv: `demo_video/.venv`, from the repo root)
`scenes/scene02 ... scene18`, then `assemble.py`. TTS: `narration.py` then `powershell -File demo_video2/tts.ps1`.
