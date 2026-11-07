# GeoLegalVault — Demo Runbook

Written from reading the code, docs and machine state on 2026-10-07. **Nothing was run or changed.**
Where I could not verify something, it says **"screenshot in rehearsal"** or **UNVERIFIED**.

**Assumptions (your brief had blanks — fix them if wrong):**
- Project: GeoLegalVault. Audience: faculty/evaluators, technical (they know web apps, some blockchain).
- Time: **10 minutes** (the length `docs/DEMO_SCRIPT.md` is written for).
- Windows 11, PowerShell. Repo root: `c:\Faizal\Block chain prj\GeoLegalVault`.

---

## 0. Read this first — three problems found on your machine and in the docs

1. **Another project is using your ports.** Containers named `proofchain-*` are running and hold ports
   **8000, 8080, 8545, 9000, 9001, 27017**. GeoLegalVault needs 8000, 9000, 9001, 27017 (and 8545 for the
   placeholder node). If you start GeoLegalVault now, it will fail or you will talk to the wrong backend.
   Fix is in Part 1, step 2.
2. **`docs/DEMO_SCRIPT.md` has a step that will fail.** It says the Legal Officer uploads, then the Legal
   Officer approves. The code forbids this: the approver must not be the uploader
   (`MAKER_CHECKER_VIOLATION`, `backend/app/core/rbac.py`). The UI hides the Approve button for the uploader.
   **This runbook uses a different role order** (Part 3).
3. **The chain setup is unknown to me.** The anchoring code reads `SEPOLIA_RPC_URL`, `SERVICE_WALLET_PRIVATE_KEY`
   and `CONTRACT_ADDRESS` from `.env`. My tooling blocked me from reading `.env` values (it holds secrets), so I do
   not know if they are real Sepolia values, local values, or placeholders. `.env` was last edited **today at
   12:49**. You must run the preflight in Part 1, step 6 to find out.

---

## Rules for the whole demo

**Never run these commands:**

| Command | Why |
|---|---|
| `docker compose down -v` (or `docker volume rm …`) | Deletes the Mongo and storage volumes. You lose users, geofence and every anchored document. |
| `docker system prune`, `docker volume prune` | Can delete the volumes and images you need. |
| `python scripts/seed.py --seed-documents` (any `--count`) | Sends **real blockchain transactions** for dozens of documents. Docs say it takes "several minutes" (`DEPLOYMENT.md`). It also spends faucet ETH. Not a live-demo command. |
| `docker compose --profile worker up …` | Starts the anchor worker. It signs and sends real transactions with your wallet key and may re-send old stuck rows (`docker-compose.yml` comment). |
| `docker compose up --build` / `docker compose build` | Rebuilds the backend image and runs `pip install`. Needs internet and can break a working image. Your image already exists. |
| `docker pull …`, `npm install`, `npm audit fix`, `pip install` | Network changes right before a demo. Only do these in Part 4 if a specific error tells you to. |
| `git pull`, `git checkout`, `git reset`, `git clean` | `demo/` is **untracked** (`?? demo/`). `git clean` would delete `demo/tamper.py`, which you need. |
| `python scripts/seed.py --email … --password …` | Creates an extra user with a password in shell history. Not needed. |
| Stopping or deleting any `proofchain-*` volume | That is a different project. Stop its containers (Part 1) but never delete its data. |

**Flags to never pass:** `-v` to `docker compose down`, `--build` to `up`, `--profile worker`, `--count` to seed.

**Say / do not say (Guardrail #6 in `CLAUDE.md`):**
- Say: "tamper-**evident**", "policy-level geofencing", "prototype".
- Never say: "tamper-proof", "military-grade", "unhackable", "guaranteed location".

**Practical rules:**
- Do the whole demo from **one fresh upload**. Do not reuse a stale document.
- Use **three separate browser windows or profiles** (one per role) so you never log in and out live.
- Access tokens last **15 minutes** (`JWT_ACCESS_TTL_MIN=15`). Log in fresh right before you start.

---

# Part 1 — Day-before and hour-before checklist

Open PowerShell. Every block below can be pasted as is.

### Step 1 — Go to the repo and check git

```powershell
cd "c:\Faizal\Block chain prj\GeoLegalVault"
git status --short
```

**Expected:** one line: `?? demo/`.
**Bad result:** any `M` or other lines means files changed since I looked. Run `git diff --stat` and find out why.

### Step 2 — Stop the other project (`proofchain`) and free the ports

First look at what is running:

```powershell
docker ps --format "table {{.Names}}`t{{.Ports}}"
```

**Expected (today):** five `proofchain-*` containers on 8000, 8080, 8545, 9000-9001, 27017.

Stop them. This stops the containers only. It does not delete data:

```powershell
docker stop proofchain-frontend-1 proofchain-backend-1 proofchain-hardhat-1 proofchain-mongo-1 proofchain-minio-1
```

**Expected:** each name printed back.
**Check the ports are free:**

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8000,9000,9001,27017,8545,5173 -ErrorAction SilentlyContinue | Select LocalPort,OwningProcess
```

**Expected:** empty output.
**Bad result:** a port is still listed. Run `Get-Process -Id <OwningProcess>` to see what owns it. If it is Docker, run `docker ps` and stop that container.

### Step 3 — Confirm Docker, tools and images

```powershell
docker version --format "{{.Server.Version}}"
docker compose version
node -v
npm -v
docker images --format "{{.Repository}}:{{.Tag}}" | Select-String "mongo:7|rustfs|aws-cli|geolegalvault-backend"
```

**Expected (what I saw today):** Docker `29.7.2`, Compose `v5.4.0`, Node `v20.20.2`, npm `10.8.2`, and these images present:
`mongo:7`, `rustfs/rustfs:1.0.1`, `amazon/aws-cli:2.27.0`, `geolegalvault-backend:latest`.
**Bad result:** an image is missing. You need internet for the first pull. Do this the day before, not the hour before.

### Step 4 — Start the stack (no build, no worker)

The compose file has no frontend service. The frontend runs separately in Step 5.

```powershell
docker compose up -d mongo storage storage-init backend
```

**Expected:** containers created/started. Do **not** add `--build`.
**Why not `hardhat-node`:** it is only a placeholder that prints a line and sleeps (`docker-compose.yml`). `backend` lists it as a dependency, so Compose starts it anyway. That is fine.

Check it:

```powershell
docker compose ps
```

**Expected:** `mongo` and `storage` show `healthy`; `backend` shows `Up`/`healthy` after a while; `storage-init` shows `Exited (0)`.
**Time:** UNVERIFIED. The backend image HEALTHCHECK allows a 10s start period (`backend/Dockerfile`). Time it in rehearsal.

### Step 5 — Check health

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
```

**Expected (from `docs/DEPLOYMENT.md`):** `status ok`, `mongo reachable`, `storage reachable`, `chain reachable`, `anchor_worker stale`.
`anchor_worker stale` is **normal** because you are not running the worker. It does not change `status`.
**Bad result:** `chain` is not `reachable`. I do not know how `/health` probes the chain (it may use `CHAIN_RPC_URL`, which in compose points at the placeholder). **Screenshot in rehearsal.** The real test is Step 8 (does an approval anchor?).
**Bad result:** `mongo` or `storage` not reachable. See Part 4.

### Step 6 — Check the chain setup without printing secrets

I could not read `.env`. This prints **only whether each value is a placeholder**, never the value:

```powershell
Get-Content .env | Where-Object { $_ -match '^(SEPOLIA_RPC_URL|SERVICE_WALLET_PRIVATE_KEY|CONTRACT_ADDRESS|CHAIN_ID|APP_ENV)=' } | ForEach-Object { $k,$v = $_ -split '=',2; "{0} -> {1}" -f $k, $(if ($v -match 'CHANGE_ME|change_me' -or $v -eq '') {'PLACEHOLDER'} elseif ($k -in 'APP_ENV','CHAIN_ID') {$v} else {'set'}) }
```

**Expected:** `APP_ENV -> development`, `CHAIN_ID -> 11155111` (Sepolia) and the other three `-> set`.
**Meaning of results:**
- Three `set` and `CHAIN_ID 11155111` → **Sepolia mode**. Anchoring needs internet and a funded wallet. Go to Step 7.
- Any `PLACEHOLDER` → anchoring is **not configured**. Approve will leave documents in `APPROVED`, never `ACTIVE`. The demo's second half (Blockchain Verification, tamper detection) cannot work. You must fix this before the demo or switch to the screenshot fallback (Part 4, last resort).
- `CHAIN_ID` not `11155111` (for example `31337`) → local Hardhat mode. The Etherscan link will **not** work (see "Honest limits").

### Step 7 — Check internet and the Sepolia wallet balance (Sepolia mode only)

```powershell
Test-Connection -ComputerName 1.1.1.1 -Count 1 -Quiet
```

**Expected:** `True` (it was `True` today).

Wallet balance: the repo has `scripts/faucet_check.py`. I did not read what it prints, so run it once and **screenshot in rehearsal**:

```powershell
.\backend\.venv\Scripts\python.exe scripts\faucet_check.py
```

**Bad result:** `ModuleNotFoundError`. The venv is missing a package. See Part 4.
**Bad result:** balance is zero. Anchors will fail with out-of-funds. Fund the wallet from a Sepolia faucet **the day before**.

### Step 8 — Check users exist (seed is safe to rerun)

The seed script skips users that already exist (`seed.py` prints "already exists — skipping"). `--demo` does not send blockchain transactions.

```powershell
.\backend\.venv\Scripts\python.exe scripts\seed.py --demo
```

**Expected (fresh DB):** five `Created … user` lines, then the credentials table and the geofence points:
`inside point: lat=11.67 lng=78.15`, `outside point: lat=11.0 lng=77.0`.
**Expected (already seeded):** `already exists — skipping` five times and `Geofence 'HQ Campus (demo)' already exists — reusing it.`
**Bad result:** connection refused on `localhost:27017` → Mongo is not up (Step 4), or your `.env` `MONGODB_URI` is not `mongodb://localhost:27017` (compose overrides it only for the container, not for this script).

### Step 9 — Start the frontend

Leave this window open the whole demo:

```powershell
cd "c:\Faizal\Block chain prj\GeoLegalVault\frontend"
npm run dev
```

**Expected:** Vite prints `Local: http://localhost:5173/`.
The frontend reads `VITE_API_BASE_URL=http://localhost:8000/api/v1` from `frontend\.env` (I read this file; it holds no secret).
**Bad result:** `Port 5173 is already in use`. Vite moves to another port and CORS will block login (`CORS_ORIGINS=http://localhost:5173` in `.env.example`). Free the port, do not use the other one.

### Step 10 — Open the login page in three windows

Use Chrome. Open three **separate profiles or one normal + two Incognito windows**:

```
http://localhost:5173/login
```

**Expected:** the page shows a headline "Document integrity you can verify." and a "Welcome back" form.

### Step 11 — FULL REHEARSAL (do it twice, per `DEMO_SCRIPT.md`)

Run Part 3 from start to end with a throwaway document. Time every step with a stopwatch and write the times in the table at the bottom of Part 3.
**Specific things to check during rehearsal:** see "Honest limits".

### Step 12 — One hour before: reset the state you need, not more

```powershell
cd "c:\Faizal\Block chain prj\GeoLegalVault"
docker compose ps
Invoke-RestMethod http://localhost:8000/api/v1/health
```

**Expected:** same as before. Do not rebuild or re-seed.
**Do not delete your rehearsal documents.** Just use a new title for the live run (for example `Faculty Demo NDA`). The Document Repository will show your rehearsal rows too. That is fine; it proves history.

### Screenshots to take as backup (during the rehearsal)

Save in a folder `demo-backup\` (do not put it in the repo; use Desktop):

1. Login page.
2. Dashboard as Authorized Staff, with the role badge visible.
3. Geofence Status page with the inside coordinates.
4. Upload form filled in, then the 201/redirect to Document Details with the **SHA-256** visible.
5. Document Details at each status: DRAFT → SUBMITTED → PENDING_APPROVAL → APPROVED → ACTIVE.
6. The Review panel ("Review decision").
7. Version History showing V1 and V2.
8. Blockchain Anchor Record (all fields, plus "Live on-chain read").
9. The Etherscan page for the transaction (Sepolia only).
10. Integrity Verification **VERIFIED** for V1.
11. Integrity Verification **MISMATCH — tamper detected** for V2, with the 3-way hash comparison.
12. Audit Logs filtered to your document.
13. The red error when outside the geofence (and the browser Sensors panel set to the outside point).
14. A terminal screenshot of the `tamper.py` output line.
15. `/api/v1/health` JSON.

---

# Part 2 — Live demo in the terminal

The terminal is used in only **two** places: show the stack is real, and do the "attack". Everything else is the browser.

> **Timing:** no timings in the docs for these commands. Time them in rehearsal. Write them in the blanks.

### Stage T1 — Show the stack is up (about 30 s, UNVERIFIED)

**SAY:** "This is a modular monolith. One API, a database, private object storage, and a smart contract. Let me show it running."

**TYPE:**

```powershell
docker compose ps
```

**Prints:** `mongo`, `storage`, `backend` Up/healthy; `storage-init` exited 0.

**TYPE:**

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
```

**Prints:** health JSON (see Part 1, Step 5).

**SAY:** "The storage bucket is private. The only way out is a short pre-signed link, 60 seconds by default."

### Stage T2 — The attack (do this at Part 3, step 16; about 10 s, UNVERIFIED)

**SAY:** "Now I act as someone with direct access to the storage server, not through the application. I change one byte of version 2."

Copy the exact V2 title first (you will type it below):

**TYPE** (replace the title; it must match exactly, including punctuation):

```powershell
cd "c:\Faizal\Block chain prj\GeoLegalVault"
.\backend\.venv\Scripts\python.exe demo\tamper.py "Faculty Demo NDA"
```

**Prints (from `demo/tamper.py`):** `Changed 1 byte of V2 of 'Faculty Demo NDA' in storage (docs/<id>/v2-<hash>).`
**Prints on a wrong title:** `No document titled 'Faculty Demo NDA'`.

**While it runs, SAY:** "This script bypasses the app on purpose. The database still holds the original hash. So does the blockchain."

**Important:** `tamper.py` tampers the **latest version**. Run it **after V2 is ACTIVE**, never before.

---

# Part 3 — Live demo in the browser

**Login password for every demo user:** `Demo@Pass123!` (set by `scripts/seed.py`).

| Window | Email | Role label | Clearance |
|---|---|---|---|
| A | `authorized_staff@geolegalvault.demo` | Authorized Staff | CONFIDENTIAL |
| B | `reviewing_officer@geolegalvault.demo` | Reviewing Officer | RESTRICTED |
| C | `legal_officer@geolegalvault.demo` | Legal Officer | RESTRICTED |
| D (optional, step 19) | `auditor@geolegalvault.demo` | Auditor | RESTRICTED |

(Clearances come from `PROPOSED_ROLE_CLEARANCE` in `backend/app/core/clearance.py`. New users get the role's value.)

**Who does what (this is why the order differs from `DEMO_SCRIPT.md`):**
Authorized Staff uploads and submits → Reviewing Officer reviews → Legal Officer approves. The approver and the reviewer must not be the uploader.

**Set Chrome location before you start, in every window that will upload or amend:**
DevTools (F12) → three-dot menu → More tools → **Sensors** → Location → Other… → Latitude `11.67`, Longitude `78.15`.
Allow the location permission when Chrome asks.
The server rejects readings with accuracy worse than **100 m** or older than **60 s** (`GEO_ACCURACY_MAX_M`, `GEO_FRESHNESS_MAX_SEC`). I do not know what accuracy Chrome's override reports. **Screenshot in rehearsal.** DevTools must stay open on that tab.

---

### Steps

**1. CLICK / TYPE — Window A: Login.**
Go to `http://localhost:5173/login`. Enter `authorized_staff@geolegalvault.demo` and `Demo@Pass123!`. Click **Sign in**.
**You should see:** the Dashboard, a "Welcome" headline, a "Location status" card, "Total documents" and "My drafts" tiles, and the role **"Authorized Staff"** in the top-right user menu.
**SAY:** "Five roles, deny-by-default. I'm Authorized Staff. The sidebar only shows what this role may do."
**Note:** the Dashboard may show an "anchor attention" banner about old stuck documents from your dev data (`DECISIONS.md` lists "Approval Demo" etc. as stuck). Only roles with anchor permissions see it. If Legal Officer sees it later, say "that's the alert for stuck anchors, a feature".

**2. CLICK — Sidebar → Geofence Status.**
**You should see:** the heading "Geofence Status" and cards **Latitude**, **Longitude**, **Accuracy**, **Reading age**, plus a **Refresh location** button. It should show `11.670000` and `78.150000`.
**SAY:** "My browser reports a location. The browser only sends a claim. The server will decide inside or outside. The client never decides."
**Note:** `DEMO_SCRIPT.md` says a green "Inside" badge appears. I did not find that label in this page's code. **Screenshot in rehearsal.** Do not promise a badge.

**3. CLICK — Sidebar → Upload.**
**You should see:** "Upload a Document", then a "Location reading: 11.67000, 78.15000 (±…m)" line with a `refresh` link.
Fill in:
- **Title:** `Faculty Demo NDA` (remember it exactly)
- **Document type:** `NDA` (placeholder text is "e.g. CONTRACT")
- **Classification:** choose a level at or below CONFIDENTIAL (the select starts at "Choose a level"; it says "You can classify up to your own clearance level"). Pick the level labelled Internal. **Level label spelling: screenshot in rehearsal.**
- **Tags:** optional.
- **File:** drop a small text or PDF file under 10 MB (`MAX_UPLOAD_MB=10`). Use a real small `.txt`. Server checks MIME vs content (`MIME_MISMATCH` exists in the history), so do not rename a PDF to `.txt`.
Click **Upload** (button label: **screenshot in rehearsal**; the code shows a submit button disabled until a file is chosen).
**SAY (during upload):** "The server checks my token, then my role, then my location, then the file itself, then it stores it, then logs it. That order is fixed."
**You should see:** redirect to Document Details with status **DRAFT** and the **SHA-256**.
**SAY:** "The file lives in private storage under a server-made key, not the original name. Only the hash, version and a few fields go on the blockchain. Never the file, never a name."

**4. CLICK — Document Details → Submit for review.**
**You should see:** status badge changes to **SUBMITTED**.
**SAY:** "Submitted. I can't approve my own work. That's separation of duties."

**5. (Optional, 30 s) — Show the immutability / maker-checker.**
Try nothing. Just point at the missing Approve/Review buttons.
**SAY:** "As the uploader I have no Review or Approve button. The server also rejects it with MAKER_CHECKER_VIOLATION."

**6. CLICK / TYPE — Window B: log in as `reviewing_officer@geolegalvault.demo`.**
Sidebar → **Document Repository** → open **Faculty Demo NDA** (columns: Title, Status, Updated).
**You should see:** status **SUBMITTED** and a **Review** button.
Click **Review**. A panel "Review decision" opens with a comment box.
Click **Approve review**.
**You should see:** status **PENDING_APPROVAL**.
**SAY:** "The reviewer approves the content. This is not the blockchain step yet."
**Note:** `DEMO_SCRIPT.md` mentions an UNDER_REVIEW status. The seed code goes SUBMITTED → PENDING_APPROVAL with no UNDER_REVIEW in between. Say only what you see.

**7. CLICK / TYPE — Window C: log in as `legal_officer@geolegalvault.demo`.**
Open the same document. Click **Approve**.
**You should see:** status goes to **APPROVED**, then **ACTIVE** once the anchor is confirmed.
**SAY:** "There is no 'anchor' button anywhere. Approval triggers anchoring automatically. The backend's own service wallet signs, never the user."
**Quiet stretch — SAY while waiting:** "Anchoring is one small transaction to a smart contract on Sepolia. It writes the document id, version, hash, event type and time. The contract refuses a second anchor for the same version."
**Timing:** `docs/DEMO_SCRIPT.md` budgets about 1 minute (4:00 → 5:00 for Submit, Review and Approve). The code retries 3 times in-request (`ANCHOR_MAX_ATTEMPTS=3`, `ANCHOR_RETRY_BACKOFF_SEC=1.0`). Actual time: **measure in rehearsal**.
**If it stays APPROVED:** go to Part 4 ("Anchor stays APPROVED").

**8. CLICK — Document Details → Version history** (link at the bottom of the button row).
**You should see:** V1 with a **Verify** button and, when anchored, a **View on-chain** button.
Click **View on-chain**.
**You should see:** page "Blockchain Anchor Record" with Status, Event type, Network, Contract address, Transaction hash, Block number, Recorded hash, Created, Confirmed. Below it "Live on-chain read": Exists on-chain, On-chain hash, Block timestamp.
**SAY:** "The recorded hash and the live on-chain hash match. The chain is read live, now."
**CLICK — Open on Etherscan** (shown only if a transaction hash exists).
**You should see (Sepolia mode):** the transaction on `sepolia.etherscan.io`.
**SAY:** "Public, immutable, independent of my database."
**Local-chain mode:** this link is **always** `https://sepolia.etherscan.io/tx/…` (hardcoded in `backend/app/modules/blockchain/models.py`). It would show "not found". Skip this click and say "this is the Sepolia explorer link".

**9. (Optional, 60 s) CLICK — back to Document Details → Download.**
A new tab opens with a pre-signed storage URL.
**SAY:** "The API never streams the file. It hands out a link that expires in about a minute."
**Risk:** the link host comes from `STORAGE_PUBLIC_ENDPOINT` (default `http://localhost:9000`). It works only if port 9000 is the GeoLegalVault storage. **Screenshot in rehearsal.**

**10. CLICK — Window C (Legal Officer): Document Details → Request amendment.**
**You should see:** the page "Amend: Faculty Demo NDA" with a reason field and a submit button.
Type a reason such as `Correcting clause 4.2 wording` and submit.
**You should see:** status **AMENDMENT_REQUESTED**, then a form to upload the corrected file.
**SAY:** "Versions are immutable. I can't edit V1. An amendment makes V2, linked to V1's hash."

**11. CLICK — Upload V2.**
Still on the amend page, choose a **different small text file** (change a few words) and upload.
**Important — who is the uploader of V2?** This is the person logged in here (Legal Officer). Then the approver of V2 must be **someone else**, and the person who submits V2 must be the V2 uploader. So:
- Legal Officer (Window C) uploads V2 and clicks **Submit for review**.
- Reviewing Officer (Window B) reviews it.
- **Authorized Staff (Window A)** cannot approve (no `approve:perform`). The approver must have APPROVE and not be the uploader. **Only Legal Officer has approve.** So the Legal Officer cannot both upload V2 and approve V2.

**Therefore: let Authorized Staff upload V2 instead.** Do step 10's "Request amendment" in Window C (Legal Officer), then **switch to Window A** (Authorized Staff), open the document, click **Upload amended version**, upload the file, and click **Submit for review** in Window A. Then Window B reviews, and Window C approves.
Authorized Staff has `document:amend` (`rbac.py`). **This V2 role order is my reading of the code. Screenshot in rehearsal that the Authorized Staff sees the "Upload amended version" button.**

**12. CLICK — Window B: review V2 → Window C: Approve V2.**
Same as steps 6 and 7. Wait for **ACTIVE**.

**13. CLICK — Version history.**
**You should see:** V1 marked **SUPERSEDED** and V2 **ACTIVE**, each with its own anchor.
**SAY:** "Two versions, two independent anchors. V2 points back to V1's hash."

**14. TYPE — Terminal (Stage T2 above).**
Run `tamper.py "Faculty Demo NDA"`.

**15. CLICK — Window C or B: Document Details → Verify** (this opens Integrity Verification for the **current** version, V2). Click **Run verification**.
**You should see:** a large banner **MISMATCH — tamper detected**, and under "3-way hash comparison": **Recomputed (current file bytes)**, **Stored (recorded at upload)**, **On-chain (Sepolia)**. Recomputed differs from the other two.
**SAY:** "The file bytes no longer match the hash recorded at upload or the hash on the chain. The system detects the change."
**SAY (say it plainly):** "It does not prevent the change. It makes it evident."
**Quiet stretch — SAY while the button says "Verifying…":** "It re-reads the file, hashes it with SHA-256, and compares three values."

**16. CLICK — Version history → V1 → Verify → Run verification.**
**You should see:** **VERIFIED** (green).
**SAY:** "V1 was never touched, and it still passes. So the mismatch above is real, not a broken check."

**17. CLICK — Sidebar → Audit Logs** (as Auditor or Administrator, **not** the roles above; Legal Officer has no `audit:view`).
Log in as `auditor@geolegalvault.demo` in Window D.
**You should see:** a table with Actor, Action, Target, Result. Filter boxes: "Action (e.g. LOGIN_SUCCESS)", "Result (e.g. SUCCESS)", "Target type (e.g. document)", "Actor id", "Target id".
Click a **Target** link (tooltip "Filter by this target") to filter to your document.
**You should see:** upload, submit, review, approve, anchor and verification rows (exact action names: **screenshot in rehearsal**; `DEMO_SCRIPT.md` lists `UPLOAD`, `SUBMIT`, `APPROVE`, `ANCHOR_OK`, `VERIFY_FAIL`, `VERIFY_PASS`).
**SAY:** "Every sensitive action is logged: who, what, when, result. Rows above the Auditor's clearance have their details withheld."
**Honest note to say if asked:** "The audit log itself has no hash chain yet. That's a documented open item (CMP-01)."

**18. (Optional, 60 s) CLICK — Outside the fence.**
In Window A DevTools → Sensors → Location → Other… → Latitude `11.00`, Longitude `77.00`. Wait a few seconds, then try **Sidebar → Upload** and submit.
**You should see:** a red error from the server with code `GEOFENCE_DENIED` (HTTP 403). The exact message text: **screenshot in rehearsal**.
**SAY:** "The server checked location itself. Editing the page in the browser doesn't change that."
**Honest limit (SAY it):** "Browser GPS can be faked. I just faked it with DevTools. This is a policy control, not a guarantee."
**Risk:** the Upload page requires a **fresh** reading. If the page still shows the old inside coordinates, click `refresh` in the location line.

**19. CLICK / SAY — Close on the limits slide (30 s).**
**SAY:** "Tamper-evident, not tamper-proof. The blockchain proves a file has not changed since anchoring. It does not stop access. Geofencing is a policy control, not a cryptographic guarantee. The access control is application-level, not encryption. This is a prototype."

### Timing table (fill in during rehearsal)

| Step | Docs say | Rehearsal 1 | Rehearsal 2 |
|---|---|---|---|
| Whole demo | 10:00 (`DEMO_SCRIPT.md`) | | |
| Upload to details page | not stated | | |
| Approve to ACTIVE | ~1:00 budget (`DEMO_SCRIPT.md`) | | |
| V2 flow (steps 10-12) | ~1:00 budget | | |
| tamper.py | not stated | | |
| Verify (MISMATCH) | not stated | | |

**The docs' 10-minute plan will not fit with the extra role switches above.** Plan on 12-15 minutes live, or pre-do V2 before the audience arrives and **start the live part at step 14** (tamper → verify). I recommend that. It is the part faculty remember.

---

# Part 4 — Contingency

| # | What you see | Cause / exact text | Fix (copy-paste) | SAY while fixing |
|---|---|---|---|---|
| 1 | `Bind for 0.0.0.0:8000 failed: port is already allocated` (or 27017 / 9000 / 9001) | The `proofchain-*` containers (or something else) hold the port. | `docker stop proofchain-frontend-1 proofchain-backend-1 proofchain-hardhat-1 proofchain-mongo-1 proofchain-minio-1` then `docker compose up -d mongo storage storage-init backend` | "A leftover container from another project. Freeing the port." |
| 2 | Login works but pages say network error / CORS error in the browser console | Vite moved off 5173, or the backend isn't running. | `Invoke-RestMethod http://localhost:8000/api/v1/health`. If it fails: `docker compose up -d backend`. If the Vite URL isn't `localhost:5173`, stop Vite, free 5173, restart `npm run dev`. | "The browser is blocking cross-origin calls. The server only allows one origin." |
| 3 | Login says invalid credentials | The demo users aren't seeded in this DB. | `.\backend\.venv\Scripts\python.exe scripts\seed.py --demo` | "Creating the demo users." |
| 4 | `connection refused` from `seed.py` or `tamper.py` | Mongo not up, or `.env` has a different `MONGODB_URI`. | `docker compose up -d mongo` then `docker compose ps` | "Starting the database." |
| 5 | `ModuleNotFoundError: No module named '…'` running a script | The venv lacks a package. **Needs internet.** | `.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt` | "Installing a missing dependency." Better: fix this in Part 1. |
| 6 | Document stays **APPROVED**, never **ACTIVE** | Anchor failed: no funds, RPC down/rate-limited, wrong chain setting, or placeholders. Fixed error code is stored, not raw text (`anchor_errors.py`). Worker is off, so nothing retries it. | Run Part 1 Step 6 and Step 7. Try the next document, or open the Dashboard anchor-attention banner (Administrator has **Retry**; this only re-queues, it doesn't send; the worker is off, so it won't resend). **Do not start the worker.** Use the screenshot fallback below. | `docs/DEMO_SCRIPT.md` allows this: "On a public testnet the document stays usable, status APPROVED, pending anchor. That is the designed failure handling. A background worker would retry it." |
| 7 | Upload / Amend returns a red **403 `GEOFENCE_DENIED`** while you are "inside" | Chrome location override is off, wrong tab, permission blocked, accuracy over 100 m, or reading older than 60 s. Also: the user has no assigned fence. | Click `refresh` on the location line. Re-check DevTools → Sensors on **this tab**. Chrome padlock → Location → Allow. Seed script assigns the fence to all five demo users. | "Our policy check is rejecting my reading. Let me fix the browser location. This is the control working." |
| 8 | Upload returns **MIME_MISMATCH** or 413 | File is a renamed type, or bigger than 10 MB. | Use a real small `.txt` file. | "The server checks file content, not the extension." |
| 9 | No Approve button for Legal Officer | That user uploaded the version (maker-checker) or status isn't PENDING_APPROVAL. | Make sure Authorized Staff uploaded, and the Reviewing Officer already clicked **Approve review**. | "The system won't let the uploader approve. That is the rule." |
| 10 | You can't open the document (looks like it doesn't exist) | **Clearance:** a document above your clearance returns "not found" on purpose (Guardrail #13). | Upload with **Internal** or lower. Authorized Staff is CONFIDENTIAL max. | "Hidden documents look identical to missing ones. That's by design." |
| 11 | Log out in the middle (session expired) | Access token TTL is 15 min. | Log in again in that window. | "Sessions are short-lived by design." |
| 12 | `tamper.py` says `No document titled '…'` | Title doesn't match exactly. | Copy the title from the Document Details heading. | "Matching the document name." |
| 13 | Verify still shows VERIFIED after `tamper.py` | You tampered an older version, or Verify was run on a different version. | Tamper hits the **latest** version. Verify the same version from Version history. | "Making sure I'm verifying the version I changed." |
| 14 | Verify shows **COULD NOT CHECK THE BLOCKCHAIN** | RPC unreachable (`CHAIN_READ_TIMEOUT_SEC=10`). | Check internet; retry **Run verification**. | "The chain read timed out. The system reports that honestly rather than guessing." |
| 15 | Verify shows **NOT ANCHORED YET** / **ANCHOR MISSING** | The version has no confirmed anchor on that chain. | Use a different, anchored document. | "This version isn't anchored yet; the system says so." |
| 16 | Download link opens an error page | `STORAGE_PUBLIC_ENDPOINT` host/port wrong or storage down. | `docker compose ps` → `storage` healthy? Skip the download step. | "Skipping the download; the next step matters more." |
| 17 | Vite fails to start | `node_modules` missing or Node version. | `node -v` (need 20+). If `node_modules` is missing, `npm install` (needs internet). | "Starting the front end." |
| 18 | Anything else breaks | — | Last resort below. | "Let me show you the recorded evidence from my test run." |

### Last resort — screenshots and saved output

1. Stop fixing. Say: "I'll walk you through the run I did earlier. Every screen is from the real system."
2. Open `Desktop\demo-backup\` and walk the 15 screenshots in order (list in Part 1).
3. Keep the **key three** ready: the **SHA-256 on Document Details**, the **Blockchain Anchor Record**, and the **MISMATCH** banner next to the **VERIFIED** banner.
4. Show the test evidence as a fallback (no stack needed): `docs/TEST_PLAN.md` and the test files in `backend\tests\`. Do **not** run `pytest` live; I did not verify how long it takes or what it needs.
5. State honestly that it's a recording. Do not present screenshots as live.

---

# Honest limits — what I could NOT verify

**Must check in rehearsal:**

| # | Not verified | Why | What to do |
|---|---|---|---|
| 1 | Whether `.env` is real Sepolia, local, or placeholder | Reading `.env` values was blocked (secrets). | Part 1, Steps 6-7. |
| 2 | Whether the wallet has funds, and whether `CONTRACT_ADDRESS` is the deployed contract | Same. I did not call the chain. | Part 1, Step 7 + a full rehearsal that reaches ACTIVE. |
| 3 | What state the Mongo volume `geolegalvault_mongo_data` is in (seeded or not, how many documents) | Mongo is stopped; I did not start anything. | Part 1, Step 8. |
| 4 | Whether `backend\.venv` has all packages | I saw the folder exists, not its contents. | Run `scripts\faucet_check.py` or `seed.py --demo`; both import app code. |
| 5 | Whether `geolegalvault-backend:latest` still starts cleanly | Image exists (494 MB); I did not start it. Its container last exited with code 137 three days ago. 137 normally means it was killed or out of memory. | Part 1, Step 4 and 5. |
| 6 | What `/health` reports for `chain` | I don't know what it probes. | Screenshot in rehearsal; trust Step 11 (real approval) over this field. |
| 7 | The Geofence Status page's "Inside" wording | `DEMO_SCRIPT.md` says a green "Inside" badge. I found coordinates and a Refresh button, not that badge. | Screenshot in rehearsal. |
| 8 | Whether Chrome's DevTools location override reports accuracy ≤ 100 m | Server rejects worse accuracy. | Try in rehearsal. |
| 9 | Exact text of the Upload submit button, the classification level labels, the sign-out menu item, the 403 error message, and the Audit Logs action names | Found in code only partly; I did not render the pages. | Screenshot in rehearsal. |
| 10 | Whether Authorized Staff sees **Upload amended version** after the Legal Officer requests an amendment | My reading of `DocumentDetails.tsx` and `rbac.py`, not a run. The V2 order in step 11 may need adjusting. | Test in rehearsal. If it fails, use Legal Officer to upload V2 and approve nothing live; show V2 as pre-made. |
| 11 | Whether the status goes through UNDER_REVIEW | Docs say yes, the seed code says no. | Say only what is on screen. |
| 12 | All timings | No timing is recorded in docs or logs for build, start, upload, approve or verify (except the 10-minute plan and the 3 in-request anchor attempts, 1 s apart). | Fill the table in Part 3. |
| 13 | A real Sepolia run end to end | `CLAUDE.md` (Guardrail #10) lists this as "not exercised". | Rehearsal. |
| 14 | Local-Hardhat mode as a demo path | Not documented for demos. It is used only by test code. The Etherscan link is hardcoded to Sepolia. I did not build steps for it because I'd be guessing. | Stay on Sepolia, or do not click the Etherscan link. |
| 15 | `demo/tamper.py` | It's **untracked** (not committed) and I did not run it. It needs the same `.env` storage and Mongo settings. | One dry attempt on a rehearsal document. |
| 16 | The `demo/latex` folder | Four `.tex` files (`nda_v1`, `nda_v2`, `service_agreement`, `board_resolution`). I did not open them. They look like source for demo documents, but I don't know if PDFs exist. | Use a small `.txt` unless you already have PDFs. |

**Known behaviours from the docs, not bugs:** `anchor_worker: stale` in `/health` when the worker is off; old stuck dev documents from August may appear in the Dashboard alert for roles with anchor view (`DECISIONS.md`).

---

# Biggest risks and what to do tonight

1. **Port conflict with `proofchain`.** Stop those containers (Part 1, Step 2). Do it tonight and again an hour before.
2. **Anchoring may not be configured.** Run the Part 1 Step 6 check. If any value is `PLACEHOLDER`, half the demo cannot run live. Decide tonight: fix it or use the screenshot fallback.
3. **`DEMO_SCRIPT.md` role order breaks maker-checker.** Use the order in Part 3: Authorized Staff uploads, Reviewing Officer reviews, Legal Officer approves.
4. **Sepolia is a public network.** It can be slow or rate-limited. Have one fully anchored V1+V2 document ready before you start, and begin the live part at the tamper step.
5. **No timings exist.** Two full rehearsals are the only way to know if you fit in 10 minutes.

**Tonight, in order:** (a) Part 1 Steps 1-9; (b) one full rehearsal with the screenshots; (c) fund the wallet if needed; (d) write your own times in the table; (e) copy `demo-backup\` to a USB stick or cloud folder.
