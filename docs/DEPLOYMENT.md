# Deployment Guide — GeoLegalVault

Target stack (Plan Part 30, ₹0 budget): frontend on **Vercel**, backend on **Render**,
metadata on **MongoDB Atlas M0**, blobs on **Cloudflare R2**, anchoring on **Sepolia**.
Local dev (`docker-compose up`) uses Mongo + MinIO + a Hardhat node instead — same
codebase, only environment variables differ.

Follow the steps **in this exact order** — later steps depend on values produced by
earlier ones (the contract address, the Atlas connection string, etc.).

## 0. Prerequisites

- A GitHub repo with this code pushed (Vercel/Render both deploy from a git repo).
- Accounts: MongoDB Atlas, Cloudflare, Render, Vercel, Alchemy (or another Sepolia RPC
  provider), a Sepolia faucet (e.g. Google Cloud's, Alchemy's, or sepoliafaucet.com).
- Node.js 20+ and Python 3.11+ available locally, to run the one-time deploy/seed scripts.

## 1. Deploy the smart contract to Sepolia

```bash
cd contracts
npm ci
npx hardhat test                 # sanity check before spending real (faucet) gas
```

Fund the **service wallet** address you intend to use from a Sepolia faucet (a few faucet
ETH is enough for hundreds of anchors — each `anchor()` call is one small `SSTORE`).

Set `SEPOLIA_RPC_URL` and `SERVICE_WALLET_PRIVATE_KEY` in the repo-root `.env` (this file
is read by `contracts/hardhat.config.ts` via `dotenv` — there is no separate
`contracts/.env`), then deploy:

```bash
npx hardhat run scripts/deploy.ts --network sepolia
```

This prints the deployed address — **record it**; the next steps and every later step
need `CONTRACT_ADDRESS` set to this value.

Optional sanity check that anchoring actually round-trips before wiring up the whole app:

```bash
cd ..
python scripts/anchor_smoke_test.py   # sends one real (throwaway) anchor tx and reads it back
```

## 2. Provision MongoDB Atlas (M0, free tier)

1. Create a free **M0** cluster.
2. Create a database user with a strong password (this becomes part of `MONGODB_URI`).
3. Network access → add the specific IP ranges you'll deploy from, or `0.0.0.0/0` only if
   you accept that trade-off for a prototype (Render's outbound IPs aren't static on the
   free tier, which is the usual reason projects at this scale allow-list broadly — note
   this explicitly as a known trade-off, not an oversight).
4. Copy the connection string → this is `MONGODB_URI`. Pick a database name (e.g.
   `geolegalvault`) → `MONGODB_DB`.

Indexes are created automatically at application startup
(`backend/app/core/db.py::ensure_indexes()`) — no manual index setup needed.

## 3. Provision Cloudflare R2 (private bucket)

1. Create an R2 bucket (e.g. `geolegalvault-prod`). Leave it **private** — do not enable
   public access.
2. Create an R2 API token scoped to just this bucket (Object Read & Write) → this gives
   you `STORAGE_ACCESS_KEY` / `STORAGE_SECRET_KEY`.
3. `STORAGE_ENDPOINT` and `STORAGE_PUBLIC_ENDPOINT` are both your R2 S3-API endpoint
   (`https://<account_id>.r2.cloudflarestorage.com`) — unlike local dev (where the backend
   reaches MinIO via a Docker-internal hostname the browser can't resolve), R2 has one
   public endpoint for both the backend and the pre-signed URLs it hands to clients.
4. `STORAGE_REGION=auto`, `STORAGE_BUCKET=<your bucket name>`.

## 4. Deploy the backend to Render

1. New **Web Service** → connect the repo → root/Dockerfile path `backend/Dockerfile`
   (Render builds and runs the Docker image directly; no build command needed).
2. Instance type: the free tier is fine for a demo (the Dockerfile's `WEB_CONCURRENCY`
   defaults to 2 gunicorn workers, sized for it).
3. Set every backend env var from `.env.example` in Render's **Environment** tab, using
   the real values from steps 1–3 above. At minimum, set `APP_ENV=production` — this makes
   the app **fail fast at startup** if any of `JWT_SECRET`, `MONGODB_URI`,
   `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `SEPOLIA_RPC_URL`,
   `SERVICE_WALLET_PRIVATE_KEY`, or `CONTRACT_ADDRESS` is still a placeholder
   (`backend/app/core/config.py`'s validator).
4. Set `CORS_ORIGINS` to your eventual Vercel URL (step 5) — you can leave this as
   `http://localhost:5173` for the first deploy and update it once you know the Vercel URL,
   then redeploy.
5. Render sets `$PORT` automatically; the Dockerfile's `CMD` already binds to it.
6. Deploy, then verify:
   ```bash
   curl https://<your-render-service>.onrender.com/api/v1/health
   # {"status":"ok","mongo":"reachable","storage":"reachable","chain":"reachable"}
   ```
7. Run the seed script **against this deployment's database** (from your local machine,
   with the repo-root `.env` pointed at the same `MONGODB_URI`/`STORAGE_*`/blockchain
   values you just set in Render — the seed script talks to Mongo/R2/Sepolia directly, not
   through the API):
   ```bash
   python scripts/seed.py --demo
   python scripts/seed.py --seed-documents
   ```
   `--seed-documents` sends real anchor transactions (one per approved version) — with the
   default `--count 35` this can take several minutes; it prints a stage-distribution
   summary and, at the end, which documents are the amendment (V1→V2) and controlled-
   tamper demo cases. See `scripts/seed.py`'s own docstring and the warning it prints if
   fewer than 10 documents reach `ACTIVE` (almost always a sign the blockchain env vars
   above aren't wired up correctly yet).

## 5. Deploy the frontend to Vercel

1. New Project → import the repo → root directory `frontend/` (Vercel auto-detects Vite).
2. Set `VITE_API_BASE_URL` to `https://<your-render-service>.onrender.com/api/v1`.
3. Deploy. Then go back to Render and set `CORS_ORIGINS` to the Vercel URL Vercel just gave
   you (e.g. `https://geolegalvault.vercel.app`), and redeploy the backend — CORS is
   locked to exactly this origin, not `*`.

## 6. Smoke test

Run through the golden path once by hand before considering the deployment done:
login → geofence status → upload (inside the fence) → submit → review → approve (watch
`blockchain_anchors` go `PENDING`→`CONFIRMED`, click the Etherscan link) → amend → verify
V2 → tamper a blob directly in the R2 console → verify V2 again (MISMATCH) → verify V1
(still VERIFIED) → check `/audit` for a matching trail → try an operation from an
out-of-geofence location (403). This is exactly `DEMO_SCRIPT.md`, minus the timing —
run it once to confirm the real deployment, then again live for the actual demo.

## 7. Observability + backup

- Set `SENTRY_DSN` in Render if you want exception monitoring (optional — the app runs
  fine with it unset; `core/sentry.py` no-ops when it's empty).
- Take a DB snapshot: Atlas takes automatic snapshots on M0's backup policy, or run
  `scripts/backup.sh` (wraps `mongodump` against `MONGODB_URI`) for a manual one before a
  demo, in case a live edit needs to be rolled back afterward.
- Confirm logs are flowing: Render's log stream shows the structured JSON request lines
  from `core/logging.py` (request id, method, path, status, duration) with 4xx/5xx
  promoted to WARN/ERROR.

## Rollback

- **Frontend/backend:** both Vercel and Render keep prior deploys — redeploy the previous
  successful build (Vercel: "Promote to Production" on an earlier deployment; Render:
  "Rollback" on an earlier deploy in the service's Deploys tab). Equivalently, revert the
  git commit/tag and push — either platform's git-triggered deploy handles the rest.
- **Contract:** the deployed `DocumentAnchor` is immutable by design — there is no
  upgrade/rollback of contract logic. If a redeploy is ever needed (e.g. a fresh testnet),
  deploy a new instance, update `CONTRACT_ADDRESS`, and treat historical anchors under the
  old address as a separate, still-independently-verifiable record (Plan Part 31: testnet
  impermanence is a documented, accepted limitation).
- **Database:** restore from the most recent Atlas snapshot or `mongodump` backup;
  corruption is independently *detectable* (not just assumed) because Verify compares
  against the immutable on-chain hash regardless of what the restored DB says.

## CI gate before any deploy

`.github/workflows/ci.yml` runs backend (pytest + ruff), contracts (Hardhat), and frontend
(eslint + vitest + build) on every PR and push to `main`. Treat a red CI run as a hard
blocker — do not deploy from a branch CI hasn't passed on. (Enabling GitHub's branch
protection to require this — "require status checks to pass" on `main` — is a one-time
manual repo-settings step; the workflow itself doesn't need any change to support it.)
