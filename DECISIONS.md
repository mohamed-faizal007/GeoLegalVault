# DECISIONS.md

A running log of non-obvious design decisions made while extending GeoLegalVault, recorded
*before* implementation. Guardrails live in [CLAUDE.md](CLAUDE.md); this file records choices
made inside them. Newest entries last.

Format: **Decision** / **Why** / **Guardrails touched** / **Not doing**.

---

## 2026-09-21 — UI role-coverage work: user edit form + geofence prerequisite (item 2)

Context: the role-coverage audit found that `PATCH /users/{id}` (role, name, assigned geofences)
has no UI, so an admin cannot assign a geofence after creating a user — and upload, download,
approve and amend all fail with `GEOFENCE_DENIED` for a user with no assigned geofence.

### D-001 — Edit users inline in the existing Users table (no new page or modal)
**Decision:** add an "Edit" row action to `UserManagementPanel` that expands an inline edit form
(name, role, assigned geofences) reusing the existing `card`, `input`, `btn-*` classes and the
same multi-select used by the create form.
**Why:** the redesign brief says not to introduce new UI patterns; the create form already
establishes the pattern.
**Not doing:** password reset, email change — the backend `UserUpdate` schema doesn't support
them and adding them is new scope (Guardrail #12).

### D-002 — Backend blocks an admin from demoting or deactivating their own account
**Decision:** `PATCH /users/{id}` returns 409 `SELF_LOCKOUT` if the target is the calling admin
and the request changes their `role` away from ADMINISTRATOR or sets `is_active: false`.
Geofence and name edits on one's own account remain allowed.
**Why:** with a single admin, either action locks everyone out of user management with no
in-app recovery. A UI-only guard is not a boundary (Guardrail #5 spirit), so it is enforced
server-side; the UI additionally disables those controls on the admin's own row for clarity.
**Guardrails touched:** #11 (RBAC-adjacent → tests in the same change).

### D-003 — Audit every user update (`USER_UPDATE`)
**Decision:** `PATCH /users/{id}` records an audit entry, like `USER_CREATE` already does.
`meta` carries changed field *names* plus `role`, `is_active` and `assigned_geofence_ids` values
when changed. It never carries `name` or any password data.
**Why:** role and geofence assignment are the inputs to RBAC and geofence decisions, and were
the only privilege-relevant admin action with no audit trail.

### D-004 — Make the geofence prerequisite visible instead of changing enforcement
**Decision:** (a) the Users table shows each user's assigned geofence names, with a
"No geofence" warning badge when none are assigned (every role has `document:view`, and
download is geofence-gated for all of them, so the warning applies to every role); (b) the `GEOFENCE_DENIED` message is extended
to say the account may have no assigned geofence and to contact an administrator.
**Why:** enforcement is already correct and server-side (Guardrail #5). The defect was that
neither the admin nor the denied user could tell *why* an action failed.
**Not doing:** auto-assigning a default geofence, or relaxing the check for any role — that
would weaken the policy control. Also not validating geofence IDs on the backend against the
geofences collection: the UI only offers real IDs, and unknown IDs already fail closed in
`check_location` (they simply never match). Revisit if an API client other than the UI appears.

---

## 2026-09-21 — Review and approval queues (item 3)

Context: the Dashboard shows "Awaiting my review" / "Awaiting my approval" / "My drafts" counts,
but all three link to the unfiltered `/documents`, so a reviewer cannot get from the number to
the list of documents it counts.

### D-005 — A queue is the existing repository with a preset filter, not a new page
**Decision:** the Document Repository reads its filters (`status`, `owner`, `query`, `doc_type`)
from the URL query string, and the Dashboard cards deep-link to it:
`/documents?status=SUBMITTED` (reviewer), `?status=PENDING_APPROVAL` (legal officer),
`?status=DRAFT&owner=me` (my drafts).
**Why:** the list endpoint already supports these filters; a separate "Review Queue" page would
duplicate the table, pagination and empty states (no new UI patterns). URL state also makes
queues bookmarkable and makes the browser Back button restore the filter.
**Not doing:** a new backend endpoint or a new sidebar entry.

### D-006 — `owner=me` is resolved in the frontend to the signed-in user's id
**Decision:** the URL carries the literal `owner=me`; the repository substitutes
`user.id` before calling `GET /documents?owner=<id>`. A user-specific id is never put in a
shareable URL, and no backend alias is added.
**Why:** the backend already scopes correctly by `owner` id; the alias is purely a link
convenience. This is a display filter, not an access control — every role's access is still
decided by RBAC on the server (Guardrail #5), and the list endpoint's visibility rules are
unchanged.

### D-007 — Queue counts are documented as "in this state", not "actionable by me"
**Decision:** the queue count and list show every document in the queue status. A Legal Officer's
approval queue can therefore include documents they uploaded themselves, which they cannot
approve (maker != checker). The detail page is where that is handled (item 4: hide Approve for
the uploader).
**Why:** the list API has no "uploaded_by != me" filter, and adding one is new backend scope
(Guardrail #12). Not doing it now; revisit if the mismatch proves confusing.

---

## 2026-09-21 — Hide Approve for the uploader; show the reviewer's comment (item 4)

Context: the Approve and Review buttons render for anyone with the permission, so an uploader
sees a button that can only return 403 `MAKER_CHECKER_VIOLATION`. Separately, a reviewer's
"changes requested" comment is written only to the audit log, which the people who must act on
it (Legal Officer / Authorized Staff) cannot read.

### D-008 — Hide Approve and Review when the signed-in user uploaded the version in flight
**Decision:** `DocumentDetails` fetches the version list (already available to every
`document:view` role) and treats the highest `version_no` as the version being processed —
the same rule the backend uses (`_current_version` in workflow.py). If its `uploaded_by` is the
current user, Approve and Review are not rendered and a one-line note explains why.
**Why:** the backend rule compares the *version's uploader*, not the document owner, so the
document's `owner_id` is the wrong thing to check (an amendment can be uploaded by someone
other than the owner). The 403 remains the real enforcement (maker != checker, Guardrail #5
spirit); this only removes a dead-end button.
**Not doing:** a backend "can I approve?" endpoint, or an `uploaded_by` field on the document.
While the versions request is loading or fails, the buttons stay hidden rather than showing
and possibly failing — fail closed in the UI too.

### D-009 — Store the review comment on the document, not the version and not on-chain
**Decision:** on `changes_requested`, `workflow.review` stores
`review_feedback: {comment, reviewer_id, at}` on the *documents* row; `submit` clears it (a
resubmission starts a fresh review). `DocumentOut` exposes `review_feedback` (comment and
timestamp only) to every role with `document:view`, and the detail page shows it while the
document is DRAFT.
**Why:** `document_versions` is insert-only apart from `status` (Guardrail #7), so the comment
cannot live there. The documents row already carries mutable workflow state. The comment
still goes to the audit log as before — the document field is a convenience copy for the
submitter, not a replacement for the audit trail. The comment never goes on-chain
(Guardrail #1).
**Trade-off accepted:** the comment is visible to anyone who can view the document, which is
the same audience that already sees its status and history. Reviewers should not put
sensitive personal data in comments; noted in the field's placeholder text.
**Guardrails touched:** #7 (respected: no version mutation), #11 (workflow change → tests in the
same change).

---

## 2026-09-21 — Audit log filters: actor, target, date range (item 5)

Context: `GET /audit` already filters by actor, target id and date range, but the page only
exposes action, result and target type, so an auditor cannot answer "what did this person do" or
"what happened to this document last week".

### D-010 — Frontend-only change; filters live in the URL
**Decision:** add actor, target id, "from" and "to" filters to `AuditLogs`, reusing the existing
filter-bar `input` pattern, and keep all audit filters in the URL query string (same approach as
D-005) so a filtered view can be bookmarked or shared between an auditor and an admin.
**Why:** the backend needs no change to support this. Access is unchanged: `audit:view` is
still enforced server-side, and the audit trail stays read-only (no write path added).

### D-011 — Dates are picked as local calendar days; "to" is inclusive of the whole day
**Decision:** the date inputs are plain calendar dates interpreted in the viewer's local time.
"From" is sent as the start of that local day and "to" as the *end* of that local day
(23:59:59.999), both as UTC ISO timestamps.
**Why:** the backend compares against `created_at` with `$gte` / `$lte`. Sending a bare date
(midnight) as "to" would silently exclude everything that happened on the selected day — an
easy way for an auditor to miss records. Rows still display in local time, so local-day
boundaries match what the auditor sees.
**Not doing:** a time-of-day picker, or a preset ("last 24h") menu — more surface than the
requirement needs (Guardrail #12).

### D-012 — Actor and target are free-text ids, and cells in the table are click-to-filter
**Decision:** the actor and target inputs accept the raw id string (the backend also matches
non-ObjectId values such as `SYSTEM`, or an email for a failed login). Clicking an actor or
target id in the table applies it as a filter. No name lookup.
**Why:** an Auditor has no `users:manage`, so the frontend cannot resolve ids to names without a
new backend endpoint exposing user data to a read-only role, which is out of scope. Click-to-
filter makes the raw ids usable without that.
**Tests:** the backend already implemented these filters but had no test for `actor_id` or the
date range, and the frontend now depends on their inclusive-boundary behaviour, so tests for
both are added in the same change (Guardrail #11 spirit).

---

## 2026-09-22 — Auditor access to Reports; geofence name/region edit (item 6)

Context: `GET /reports/summary` is already gated to `AUDIT_VIEW` server-side (Administrator +
Auditor), but the `/admin` route and its sidebar link are gated to `USERS_MANAGE` only, so an
Auditor gets bounced to `/forbidden` before ever seeing the Reports tab they already have
permission for. Separately, `GeofenceManagementPanel` can create a geofence and toggle
`active`, but there's no way to fix a geofence's name or fix/adjust its region polygon short of
deleting and recreating it — and there's no hard delete (Guardrail #7-adjacent: no destructive
rewrite path is wanted here either).

### D-013 — `/admin` and its nav link become permission-aware per tab, not all-or-nothing
**Decision:** `ProtectedRoute` and the `Sidebar` nav item gain an optional `permissions?:
Permission[]` (any-of) alongside the existing single `permission?:`. The `/admin` route and its
sidebar link use `permissions: [USERS_MANAGE, GEOFENCE_MANAGE, AUDIT_VIEW]`. Inside
`AdminPanel`, each tab is now paired with the one permission that backs it (Users→
`USERS_MANAGE`, Geofences→`GEOFENCE_MANAGE`, Reports→`AUDIT_VIEW`, System Health→
`USERS_MANAGE`, unchanged — `/health` is a public liveness check but showing it to an Auditor is
new scope item 6 didn't ask for, Guardrail #12), the tab list is filtered by
`hasPermission(user.role, ...)`, and the selected tab defaults to the first one visible instead
of a hardcoded `"Users"`.
**Alternatives considered:**
1. A separate `/reports` route/page outside `AdminPanel` just for Auditor. Rejected: duplicates
   the container `ReportsPanel` already has, adds a second nav entry for what's otherwise the
   same panel, and D-005 already set the precedent of not building a new page/pattern when the
   existing one can be reused (here, via permission-aware tabs instead of a URL filter).
2. Loosen the backend's reports permission. Rejected — not the bug; `AUDIT_VIEW` already covers
   Auditor server-side (Guardrail #5: server is already correct, only the UI was blocking).
**Why:** an all-or-nothing `/admin` gate only worked because, until now, only Administrator held
any admin-tab permission. Making the gate and the tabs both permission-aware (rather than
special-casing "Auditor gets in but only sees one tab") means a future role with a subset of
admin permissions works without more plumbing.
**Not doing:** per-tab route paths (e.g. `/admin/reports`) — the existing tab-state-in-component
pattern (D-005/D-010 established URL-driven filters for lists, not for this kind of panel
switch) is left as-is; only its gating changes.

### D-014 — Geofence name/region edit reuses the D-001 inline-edit-in-table pattern
**Decision:** add an "Edit" row action to `GeofenceManagementPanel`, mirroring `UserEditForm`
exactly: an inline form (name input + the existing ring textarea/`parseRing` helper, now shared
between create and edit) that `PATCH`es `{name, region}` via the already-existing
`updateGeofence`. The ring textarea is pre-filled from the fence's current
`region.coordinates[0]`.
**Alternatives considered:**
1. A modal dialog. Rejected — no modal pattern exists anywhere in this app; D-001 already chose
   inline-in-table specifically to avoid introducing one.
2. Also expose `center`/`radius_m` editing (the backend schema supports both). Rejected as new
   scope — item 6 asks for name and region only, and the create form doesn't set them either
   (Guardrail #12); revisit together if a later item needs them.
**Backend:** no schema/endpoint change needed — `PATCH /geofences/{id}` already accepts
`name`/`region` and validates the polygon (closed ring, vertex cap, lng/lat range per
Guardrail #9) exactly as `POST` does.
**Found in passing — fixed in this change:** `update_geofence` had no audit call at all (unlike
`create_geofence`'s `GEOFENCE_CREATE`), and had zero test coverage beyond the `active` toggle
implicitly exercised in `test_admin_can_create_list_get_and_deactivate_geofence`. Since this
change makes `PATCH` a regularly-used edit path (not just an occasional deactivate), it now
records `GEOFENCE_UPDATE` on any applied update, with `meta: {"fields": [...]}` plus `name`
when changed — mirroring D-003's "field names always, a few safe values, never bulk/PII data"
rule (here: never the raw polygon coordinates, which are bulky and not useful in an audit
listing). A test for the new audit entry is added in the same change (Guardrail #11).
**Guardrails touched:** #9 (respected: edit form still produces `[lng, lat]` positions through
the same `parseRing`/schema validation as create), #11 (audit + tests added with the code).

---

## 2026-09-22 — A2: corrected-file upload for DRAFT-after-changes-requested; submit by
## current-version-uploader (item 7)

Context: when a Reviewing Officer requests changes, `workflow.review` loops the document
straight back to `DRAFT` (Plan Part 5: `SUBMITTED -> UNDER_REVIEW -> CHANGES_REQUESTED ->
DRAFT`) and stores the comment via `review_feedback` (item 4, D-009). But there is no way to
actually fix the file: `DocumentDetails` only offers "Submit for review" in `DRAFT`, which
resubmits the *same* version unchanged, and the one endpoint that accepts a new file
(`POST /documents` with `amend_of`) is hard-gated to `document.status == AMENDMENT_REQUESTED`
— a status that only exists on the `ACTIVE -> AMENDMENT_REQUESTED` path, not this one. Separately
(noted after item 4/D-008), `submit()` still authorizes by `document.owner_id`, but the backend's
own maker/checker rule already treats *the current version's uploader* as the relevant actor —
so once a corrected file can be uploaded by someone other than the original owner (any
`DOCUMENT_AMEND`-holding role: Legal Officer or Authorized Staff), that uploader must also be
able to submit what they just uploaded.

### D-015 — Reuse `create_next_version`/`amend_of` for the DRAFT-after-changes-requested case,
gated on `review_feedback` being set (not on `DRAFT` alone)
**Decision:** `POST /documents` (with `amend_of`) accepts the upload when
`status == AMENDMENT_REQUESTED` **or** (`status == DRAFT` **and** `review_feedback is not
None`). A no-feedback `DRAFT` (a brand-new document that was never submitted) still can't take
this path — that's a different, not-currently-requested feature (replacing V1 pre-submission),
and leaving it out keeps the change scoped to the actual gap (Guardrail #12). The endpoint
inserts V(n+1) exactly as the existing amendment path does (`create_next_version`, insert-only,
Guardrail #7) and leaves status at `DRAFT`, so the existing `canSubmit` path resubmits the new
version next.
**Alternatives considered:**
1. Gate on `status == DRAFT` alone, no `review_feedback` check. Rejected — silently also enables
   "replace V1 before ever submitting," which nobody asked for and which the create-form (not
   this endpoint) already covers by construction (Guardrail #12).
2. A new dedicated endpoint (e.g. `POST /documents/{id}/correct`) instead of extending
   `amend_of`. Rejected — `create_next_version` is exactly the right operation (insert V(n+1),
   status stays DRAFT) with no field or behavior AMENDMENT_REQUESTED's use of it doesn't already
   need; a second endpoint would duplicate validation, geofence and RBAC wiring for no gain.
**Guardrails touched:** #7 (respected — still insert-only via `create_next_version`), #5
(respected — same `DOCUMENT_AMEND` + geofence dependencies as the existing amend upload path).

### D-016 — `submit()` authorizes by the current version's uploader, not `document.owner_id`
**Decision:** `workflow.submit` now checks `version["uploaded_by"] == actor["_id"]` (fetching
the current version first, same as `review`/`approve` already do for maker≠checker), instead of
`document["owner_id"]`.
**Why:** this mirrors D-008's finding exactly — the backend's own rule for "whose action is
this" is already the version's uploader, not the document's original owner, because an
amendment (now including a changes-requested correction) can be uploaded by someone other than
whoever created the document. Leaving `submit` on `owner_id` would mean the very corrected file
just enabled by D-015 could be uploaded but never submitted by its own uploader if that uploader
isn't the document's original owner.
**Not doing:** changing `document.owner_id` itself, or adding an `uploaded_by`-style field to
the document (D-008 already declined this) — the version already carries the field `submit`
needs.
**Guardrails touched:** #11 (workflow change → tests in the same change).

### D-017 — Frontend: a new "Upload corrected file" action, gated on `review_feedback`
present; `canSubmit` now checks the current version's uploader
**Decision:** (a) `AmendmentRequest` (the existing `/documents/:id/amend` page) treats
`status === "AMENDMENT_REQUESTED" || (status === "DRAFT" && review_feedback present)` as
"ready for new version" and shows the same upload form either way — no new page (reuse
`FileDropzone`/`LocationGate`, same pattern D-005/D-001 established). `DocumentDetails` gains an
"Upload corrected file" button next to the changes-requested notice, visible under the same
condition, linking to the same `/amend` route. (b) `canSubmit` now also fetches the version list
(extending the existing `maybeCheckable` versions fetch to include `status === "DRAFT"`) and
requires the signed-in user to be the current version's uploader, not `doc.owner_id === user.id`
— matching D-008's `isUploader` computation already used for the review/approve buttons.
**Not doing:** removing the "Reason for amendment" form or its `ACTIVE`-only trigger — that path
is unchanged; only the "ready for new version" condition gains the second case.

---

## 2026-10-01 — Hygiene batch from PRODUCTION_READINESS.md (OPS-05, SEC-08, SEC-07, test infra)

Context: first batch of fixes after the production-readiness audit. Deliberately small and
behaviour-preserving apart from (c); the larger items (REL-02/03, REL-01, REL-04, SEC-02, …)
follow separately, each with its own entries.

### D-018 — Fix the 3 ruff E501 errors by wrapping the lines (no rule changes)
**Decision:** wrap the three over-long lines in `tests/api/test_geofences.py` and
`tests/integration/test_workflow.py`. Keep `line-length = 100` and the selected rule set.
**Why:** CI's "Ruff lint" step is a hard gate and was red at HEAD; DEPLOYMENT.md says a red CI run
blocks deploys. Loosening the rule would hide the next violation instead of fixing this one.
**Not doing:** adding `# noqa`, raising line length, or touching any non-test file.

### D-019 — Upgrade PyJWT, python-multipart, pytest (+ pytest-asyncio) to patched versions
**Decision:** `pyjwt` 2.10.1 → 2.15.1, `python-multipart` 0.0.20 → 0.0.32, `pytest` 8.3.4 →
9.0.3 (dev), and `pytest-asyncio` 0.25.0 → 1.3.0 because 0.25.0 declares `pytest<9`.
Exact `==` pins are kept (the repo's existing convention). Full backend suite run afterwards; any
breakage is reported rather than papered over.
**Why:** `pip-audit` found 34 known vulnerabilities across these three packages; PyJWT sits on
the auth path and python-multipart parses every upload. Fixed versions per pip-audit: PyJWT ≥ 2.15.0,
python-multipart ≥ 0.0.31, pytest ≥ 9.0.3.
**Trade-off accepted:** pytest-asyncio 1.x is a major bump; the suite's session-loop setup
(`asyncio_default_fixture_loop_scope`, `loop_scope="session"` markers) is supported there but is the
most likely thing to break, so it gets verified first.
**Not doing:** `pip-audit --no-deps` only covered pinned packages; transitive packages are not
touched here, and adding `pip-audit` to CI is a separate item.

### D-020 — Anchor errors: store/return a fixed error code, log the redacted detail server-side
**Decision:** (1) New `classify_anchor_error(exc)` maps a send/RPC failure to a short fixed code
(`RPC_UNREACHABLE`, `INSUFFICIENT_FUNDS`, `ALREADY_ANCHORED`, `REVERTED`, `NOT_CONFIGURED`,
`ANCHOR_FAILED`). That code — never `str(exc)` — is what goes into `blockchain_anchors.error`,
the `ANCHOR_FAIL` audit `meta`, and `AnchorOut.error`. (2) The full exception text is logged
server-side at ERROR with the RPC URL's secret parts masked (`redact_secrets`). (3) The API also
sanitises on read: a stored `error` that is not a known code (rows written before this change)
is returned as `ANCHOR_FAILED`.
**Why:** web3 connection errors embed the request URL, and Alchemy/Infura put the API key in the
URL path; the raw string was served to every `document:view` role and to Auditors (SEC-07).
Sanitising on read is needed because existing rows already contain raw text.
**Deviation from "log the full error":** the logged text is the full error *with the URL path /
configured RPC URL / `/v2/<key>` segments masked*. Logs ship to third parties (Render, Sentry) and
CLAUDE.md #2 says never log secret values, so logging the unmasked text would just move the leak.
**Guardrails touched:** #2 (this is the fix), #11 (blockchain service change → tests in the same
change, including a regression test that the key never reaches an API response).
**Not doing:** rewriting existing DB rows (read-side sanitising is enough and mutates nothing);
changing the anchor retry behaviour (that is REL-01, a separate item).
**Existing-test change:** `test_reanchor_same_document_version_fails_and_records_failed` asserted
the raw revert text (`"already anchored" in error`); it now asserts the `ALREADY_ANCHORED` code.

### D-021 — Hardhat-node test fixture timeout: diagnosis only, fix proposed, NOT implemented
**Finding:** not a real product problem; a flaky-under-load test setup. In isolation the
session fixture's setup (spawn `npx hardhat node` + poll + deploy) takes 5.2–5.9 s (3/3 runs); the
audited full run errored once, when a frontend build and `tsc` were saturating the CPU (the machine
also had ~1.5 GB free RAM). Later tests in the same run that needed the chain passed.
**Proposed fix (awaiting review, no code change yet):** keep the 90 s default; make it
`HARDHAT_START_TIMEOUT_SEC`-overridable for slow CI; reuse one `httpx.Client` for the readiness poll
(each bare `httpx.post` rebuilds an SSL context, which is ~1 s of CPU on this machine under load);
on timeout include the node log tail and process state in the error; retry the spawn once on a new
port before failing.
**Why not just raise the timeout:** a longer timeout only hides contention and makes real hangs slower
to report.

### Outcome of the 2026-10-01 hygiene batch (D-018..D-021)
Verified with exit codes: backend `pytest` 0 (150 passed, 93.58 % coverage), `ruff check app tests` 0,
`pip-audit -r requirements.txt --no-deps` 0 (no known vulnerabilities), frontend `tsc -b` 0,
`eslint .` 0, `vitest run` 0 (53 passed). No suite breakage from the PyJWT / python-multipart /
pytest 9 / pytest-asyncio 1.x bump. One new, expected signal: PyJWT ≥ 2.15 emits
`InsecureKeyLengthWarning` for HMAC keys < 32 bytes; the tests (and the dev `.env`) use the 9-byte
`change_me` placeholder. Not silenced — it is evidence for SEC-09 (enforce a minimum JWT secret length
outside development), which is a later item. D-021 (Hardhat fixture) remains proposal-only.

---

## 2026-10-01 — Item 1: concurrent transitions (REL-02) + upload overwrite (REL-03) + clearing TAMPERED

Context (reproduced in PRODUCTION_READINESS.md R9–R11): 4 concurrent approvals → 3 `APPROVE` audit rows,
7 anchor rows, spurious `ANCHOR_FAIL` entries; two concurrent amendment uploads → one HTTP 500 and the
survivor's DB hash ≠ the stored bytes (the second `put_object` overwrote the first's object at
`docs/{id}/v{n}`), after which the version is approved, anchored, verifies `MISMATCH`, flags the document
`TAMPERED`, and nothing can clear the flag.

### D-022 — Root cause and the alternatives considered
Two distinct races share one pattern — *read, decide, then write unconditionally* — but need different
fixes because one is about **who gets to act** (state machine) and the other about **where bytes go**
(storage namespace).

| # | Alternative | Verdict |
|---|---|---|
| 1 | **Atomic conditional update (compare-and-swap) on `documents.status`**: `find_one_and_update({_id, status: expected}, {$set: new})`; the one request that matches proceeds, everyone else gets 409. | **Adopt** for every transition. MongoDB is the arbiter, so it holds across gunicorn workers and instances (an in-process lock does not). No new infrastructure, no schema change. |
| 2 | Per-document lock (asyncio lock, or a Mongo lease document). | Reject. In-process locks fail with `WEB_CONCURRENCY=2`; a Mongo lease adds expiry/cleanup/crash-recovery states and would be held across the chain call (seconds), blocking others on the same document. |
| 3 | Optimistic concurrency with a `rev` field on every write path. | Reject for now. Every state change here is already status-driven, so status *is* the revision for the state machine; a `rev` would add plumbing to every writer without closing anything alternative 1 leaves open. Revisit if non-status mutations start to race. |
| 4 | Multi-document Mongo transactions. | Reject. Needs a replica set; local docker-compose runs a standalone `mongo:7`. |
| 5 | **Unique index**: `(document_id, version_no)` already exists; add a **partial unique index** so a version has at most one *live* (PENDING/CONFIRMED) anchor row. | **Adopt as defence in depth** behind alternative 1 (a duplicate then fails loudly instead of silently double-recording). |
| 6 | **Content-addressed storage keys**: `docs/{document_id}/v{n}-{sha256}`. Different bytes can never share a key, so an upload cannot overwrite an existing object (identical bytes → identical key → overwriting is a no-op). | **Adopt** for REL-03. Needs no coordination between uploaders and no extra state. Cost: a lost race leaves an orphan blob (deleted best-effort), and the key format changes — old rows keep their stored `storage_key`, and nothing derives a key from `version_no` at read time (checked), so old objects stay valid. |
| 7 | Reserve-then-write (insert the version row as `UPLOADING`, write the object, flip to `DRAFT`). | Reject. Adds a lifecycle state and crash-cleanup for no benefit once keys are content-addressed. |
| 8 | Conditional PUT (`If-None-Match: *`) at the object store. | Not relied on. MinIO supports it; Cloudflare R2 behaviour is unverified. Could be added later as belt-and-braces. |
| 9 | Client `Idempotency-Key` header. | Not needed: the server can recognise an identical retry itself (D-024). |

**Decision:** 1 + 5 + 6, plus natural idempotency for identical retries. Why for this project: the lifecycle
is a status machine on one Mongo collection, so a CAS on `status` is the smallest change that serialises it;
the immutability story (Guardrail #7) is about stored bytes, so making overwrite *impossible by
construction* beats trying to serialise uploaders; and none of it needs Redis, a replica set, or a second
service (Guardrail #10).
**Guardrails touched:** #7 (strengthened: a stored object is never overwritten by different content),
#3/#5 (unchanged: anchoring still only follows `approve`, pipeline order untouched), #11 (workflow state
machine + storage keys → tests in the same change, including real concurrency tests).
**Not doing:** touching `document_versions` fields other than the whitelisted status/anchor ones; changing
the retry loop's behaviour when the chain is down (REL-01); rewriting existing rows or objects.

### D-023 — Transition mechanics (REL-02)
**Decision:** add `documents.service.claim_status(db, document_id, expected, new)` (CAS; returns the updated
row or `None`). Every workflow transition claims first, then does its dependent writes, so only the winner
writes version status, audit rows, or touches the chain:
`submit` DRAFT→SUBMITTED · `review` SUBMITTED→UNDER_REVIEW (the claim; PENDING_APPROVAL or back-to-DRAFT
follow for the winner only) · **`approve` PENDING_APPROVAL→APPROVED *before* the first anchor attempt** ·
`request_amendment` ACTIVE→AMENDMENT_REQUESTED · `archive` ACTIVE→ARCHIVED. A lost claim raises the existing
`409 ILLEGAL_TRANSITION`. The read-time `_require_status` stays as a fast, descriptive pre-check.
`blockchain_service.mark_confirmed` becomes a claim too (`PENDING`→`CONFIRMED`, returns whether this call won)
and `promote_confirmed_anchor` does nothing further when it lost, so a worker pass and `approve()`'s own
confirm loop can no longer both promote (previously a double `ANCHOR_OK`/`ACTIVATE`).
**Anchor rows:** new field `live` (`True` on PENDING/CONFIRMED rows, cleared by `mark_failed`; FAILED rows
never set it) with a partial unique index `{version_id: 1}` where `live == True` (equality-only partial
filters are supported by every Mongo version we target). Existing rows lack the field and so sit outside the
index — no startup failure on legacy data, no backfill. If a duplicate live insert ever happens, the
existing live row is returned and a warning is logged.
**Not doing:** collapsing `review`'s intermediate UNDER_REVIEW state (Plan Part 5); changing retry counts.

### D-024 — Upload/amend mechanics (REL-03)
**Decision:** `storage.build_version_key(document_id, version_no, sha256)` → `docs/{id}/v{n}-{sha256}`
(`sha256` is computed before the write, as it already was). In `create_next_version` the object is written to
its content-addressed key, then the version row is inserted. If the insert hits the
`(document_id, version_no)` unique index: load the winning row; **if it has the same sha256 and the same
uploader, the retry is idempotent** and the winner's result is returned (a double-click yields one version
and two identical 201s); otherwise raise `409 VERSION_CONFLICT` and delete our object *only if its key differs
from the winner's*. Any other insert failure also deletes the orphan object. The V1 path
(`create_document_with_v1`, a brand-new ObjectId) cannot race but gets the same orphan cleanup on failure.
**Guardrails touched:** #7, #4 (keys still server-generated; still no byte proxying).
**Existing-test change:** assertions that pinned the old key format (`docs/{id}/v1`) now assert
`docs/{id}/v1-{sha256}`. THREAT_MODEL row 8 and DB_DESIGN.md are updated to match.
**Known limitation (stated, not fixed):** versions already corrupted by the old race (DB hash ≠ object)
stay corrupted; nothing here repairs them (see D-025: they will correctly refuse to clear).

### D-025 — Clearing a TAMPERED flag: `POST /documents/{id}/integrity/clear`
**Decision:** administrator-only, new permission `integrity:clear` (held only by ADMINISTRATOR; the exact-map
RBAC tests are updated in the same change). Body `{reason}` (10–1000 chars, required). Flow:
1. the document must carry `integrity_flag == "TAMPERED"` (else `409 NOT_FLAGGED`);
2. **re-run the real verification** (`verify_service.verify_version`, so each run writes its normal
   verification record and `VERIFY_*` audit row) on **every anchored version of the document**; the clear is
   allowed only if **every one returns `VERIFIED`**. Any other outcome — `MISMATCH`, `NOT_ANCHORED` for a
   version the DB says is anchored, chain/storage unreachable — refuses with `409 INTEGRITY_STILL_FAILING`
   (listing version numbers and results) and writes an `INTEGRITY_CLEAR_REFUSED` audit row;
3. otherwise clear atomically with a conditional update keyed on the `updated_at` read *before*
   verification (if anything touched the document meanwhile → `409`, retry), record `{by, at, reason}` on the
   document row (`integrity_cleared`), and write `INTEGRITY_CLEARED` with the reason and verified versions.
**Why every anchored version, not just the one that flagged:** the flag does not record which version
tripped it, and a narrower check would let a real mismatch on another version be hidden.
**Consequence to be aware of:** the intended use is "bytes were restored from backup / a transient storage
error cleared". Versions already corrupted by the old REL-03 race can never verify, so those documents
correctly cannot be cleared; remediation is out of scope here and needs a decision.
**Not geofenced:** like verify and archive, it is an administrative integrity action, not one of the
upload/approve/amend/download operations CLAUDE.md #5 treats as sensitive; RBAC, audit and re-verification are
the controls.
**Reason text** is stored in the audit row as-is (admin-entered; the UI warns not to include personal data,
as with D-009).

### D-021 (update) — Hardhat fixture hardening: approved and implemented in this round
Approved by the owner. Implemented in `tests/integration/test_anchor.py` only (a separable change):
`HARDHAT_START_TIMEOUT_SEC` env override (default 90); one reused `httpx.Client` for readiness polling;
node-log tail and process state in the timeout error; one retry on a new port before failing.

### Outcome of item 1 (D-021 update, D-022..D-025)
Verified with exit codes: backend `pytest` 0 (175 passed, 93.69 % coverage), `ruff check app tests` 0,
`pip-audit -r requirements.txt --no-deps` 0, frontend `tsc -b` 0, `eslint .` 0, `vitest run` 0 (57 passed).
**Test sensitivity check:** with the compare-and-swap reverted to an unconditional update and the key format
reverted to `docs/{id}/v{n}` (temporarily, files restored and md5-verified), 5 of the 6 new concurrency tests
fail (concurrent approvals, conflicting reviews, double submit, amendment overwrite, key collision); the
sixth (identical-retry idempotency) tests new behaviour and passes either way. The races reproduce reliably
under `asyncio.gather` because every handler yields at its Mongo/storage awaits.
**Not covered / limits:** all concurrency is single-process (one event loop, real Mongo/MinIO/Hardhat); the
cross-process guarantee rests on MongoDB's atomic `findOneAndUpdate` and unique indexes, not on a
multi-worker test. Legacy anchor rows have no `live` field (outside the unique index, by design). Versions
already corrupted by the old race remain corrupted and cannot be cleared (they correctly fail verification).

## 2026-10-03 — Step 1: legacy storage keys (follow-up to D-024)

### D-026 — Old-format keys keep working; pinned by a test, no code change
**Question:** after D-024 changed new keys to `docs/{id}/v{n}-{sha256}`, do versions stored under the old
`docs/{id}/v{n}` key still download and verify?
**Finding:** yes by construction. Download (`documents/router.py:222`) and verify (`verify/service.py:111`) both
read `version["storage_key"]` from the stored row; `build_version_key` is only called when writing a new object.
No code path derives a key from `(document_id, version_no)` for an existing version.
**Alternatives:** (a) assume it from the code reading — no regression guard; (b) migrate old objects/rows to the
new format — touches immutable `document_versions.storage_key` (Guardrail #7) for no benefit; (c) **add a test
that stores an object under the legacy key, points the row at it, removes the new-format object, and asserts
download + verify (VERIFIED) still work.** Chosen: (c).
**Guardrails touched:** #7 (the test rewrites `storage_key` directly in Mongo, test-only, to simulate pre-D-024
data; no production write path is added), #11.
**Not doing:** any migration or backfill.

## 2026-10-03 — Step 2: guardrails #9 and #5

### D-027 — Guardrail #9 (swapped `[lat, lng]`): what range checks can and cannot catch
**What is true today.** `_validate_position` checks lng ∈ [-180, 180] and lat ∈ [-90, 90]. A swapped pair
`[lat, lng]` is read as `lng' = lat, lat' = lng`. That fails the range check **only when the real longitude
has |lng| > 90** (e.g. the US, most of Asia-Pacific). When |real lng| ≤ 90 the swapped pair is a perfectly
valid coordinate and **cannot be detected from the numbers alone** — this includes the seeded demo region
(HQ ≈ 78.2°E, 11.7°N → swapped is 11.7°E, 78.2°N, a valid point in the Arctic) and all of Europe/Africa/India.
Existing wording in `schemas.py` ("so an accidental lat/lng swap … is rejected") overstates this and is
corrected as part of this change.
**Alternatives**
1. *Optional configured bounding box* (`GEOFENCE_ALLOWED_BBOX=minLng,minLat,maxLng,maxLat`): every polygon
   vertex (and `center`) must lie inside it, on create and update, server-side. Catches a swap iff the
   transposed vertices fall outside the box — true for any region whose box does not overlap its own
   transpose (India box 68–98°E × 6–36°N: swapped points have lng ≈ 11, outside → rejected). **Misses** a swap
   when every transposed vertex also lies in the box (box ⊇ its transpose, or the fence sits near the lat = lng
   diagonal), and every *non*-swap error that stays inside the box (wrong city, typo). Off by default, because
   the deployment region is unknown; protects nothing until configured.
2. *Admin preview / confirmation*: the Geofences form shows a live readout of what the ring means
   (centroid as `11.71°N 78.21°E`, bounding extent) and requires a confirm tick before save. Works for every
   case a human would recognise (centroid in the Arctic), but is **advisory and UI-only**: a direct API caller
   skips it, and a tired admin may tick through it. No map library needed (text readout only).
3. *Reject by centroid outside an expected region*: strictly weaker than (1) (checks one point, not every
   vertex) and needs the same configuration. Not chosen separately.
4. *Ring orientation heuristic* (a reflection across y = x flips winding): unreliable — GeoJSON producers
   disagree on winding and valid CW polygons would be rejected. Not chosen.
5. *Nothing beyond range checks, fix the wording only.*
**Decision:** (1) + (2). (1) is the only server-side enforcement that can catch an in-range swap and is cheap;
(2) covers the unconfigured case with a human check and is explicitly labelled advisory. At startup, when
`APP_ENV != development` and no bbox is set, log a warning (not a failure: the region is a deployment choice).
Invalid bbox config (wrong count, min ≥ max, out-of-range) fails settings load — same class of bug as #9.
Violation → `422 GEOFENCE_OUTSIDE_REGION` listing the first offending vertex.
**Claim policy:** nothing says a swap is "caught" without the qualifier. Tests pin both sides: caught (|lng| > 90
without any bbox; India swap with a bbox) and **not caught** (India swap without a bbox → accepted; a
diagonal fence with a box covering its transpose → accepted), so the limit is documented in the suite.
**Guardrails touched:** #9 (strengthened, wording corrected), #6 (no overstated claims), #11 (tests with change).
**Not doing:** a map widget, reverse geocoding, server-enforced confirmation tokens, orientation checks.

### D-028 — Guardrail #5: size limit before the body is read; auth before the multipart body is parsed
**What is true today.** FastAPI parses the request body (`request.form()` / `request.json()`) *before* it
resolves dependencies, so `POST /documents` buffered/spooled the whole multipart body before JWT, RBAC or
geofence ran; the 10 MB check happened only after `await file.read()`. An unauthenticated client could make the
server read an arbitrarily large body (no cap anywhere). Also the geofence dependency falls back to
`request.form()` when the location headers are absent (runs after JWT/RBAC, before the geofence decision).
**Alternatives**
1. *ASGI size-cap middleware only*: bounds memory/disk, but an unauthenticated client can still make us read up
   to the cap on every request.
2. *Middleware + restructure the upload route* so JWT → RBAC → geofence dependencies run first and the
   multipart body is parsed manually afterwards (`await request.form()` inside the handler; no `File()/Form()`
   parameters; `openapi_extra` keeps the documented request schema). Unauthenticated callers never cause the
   body to be read.
3. *Rely on a reverse proxy* (nginx `client_max_body_size`, Cloudflare): deployment-dependent and not in the
   repo; keep as defence in depth, not as the control.
4. *Stream straight to storage*: the SHA-256 and MIME sniff need the bytes; this is the REL-05 redesign. Out of
   scope.
**Decision:** (2). A pure-ASGI middleware (outermost) enforces a per-route cap:
`POST /api/v1/documents` → `MAX_UPLOAD_MB` MiB + 1 MiB multipart overhead; every other request →
`MAX_JSON_BODY_KB` (default 1024). (i) `Content-Length` present and over the cap → `413 PAYLOAD_TOO_LARGE`
before any read; non-numeric → 400. (ii) Otherwise bytes are counted as `receive()` delivers them; on crossing
the cap the middleware sends the 413 itself, tells the app the client disconnected (so FastAPI stops reading),
and swallows everything the app emits afterwards. This covers chunked bodies and a `Content-Length` that
understates the body. The existing exact-size check (`FILE_TOO_LARGE`, 413, file > `MAX_UPLOAD_MB`) stays.
**Residuals, stated honestly**
- Size rejection happens *before* auth (a 413 reveals nothing and is the point of rejecting early); an
  unauthenticated oversized request gets 413, an unauthenticated in-limit one gets 401 without its body read.
- JSON routes (≤ 1 MiB) are still parsed by FastAPI before their dependencies run; bounded, and login needs its
  body before auth by definition. Only the multipart upload route is reordered.
- The geofence form fallback still parses the (capped) multipart body after JWT/RBAC; it only triggers when the
  location headers are missing.
- A real HTTP server (h11/httptools) already stops at `Content-Length` bytes, so an understated length is
  mostly an ASGI-level concern (other servers/transports, direct ASGI callers); chunked/no-length bodies are the
  realistic path. Tests exercise the ASGI layer; one manual check against real uvicorn is recorded in the outcome.
- Slow-body (slowloris) is not addressed here (server/proxy timeouts).
- `JSONLoggingMiddleware` sits inside the cap and may log the aborted request with the app's view of it.
**Guardrails touched:** #5 (pipeline order made true for uploads), #2/#4 unchanged, #11 (tests with the change).
**Not doing:** streaming uploads to storage, per-IP byte budgets, changing the 10 MB product limit.

## 2026-10-04 — Step 2 follow-ups

### D-029 — Amendment race: the next version number comes from the validated document, not a fresh read
**Found by** the full backend suite: `test_concurrent_identical_amendment_upload_is_idempotent` fails
deterministically at the D-024 commit when run alone (6/6) and intermittently in the full run. Cause: the
router validates `status == AMENDMENT_REQUESTED` on the row it read, then `create_next_version` *re-reads* the
latest version to pick `next_version_no`. If an identical request finished in between, the late one sees V2 as
latest and creates V3 (same bytes, 201) — two versions from one double-click. D-024's idempotency only covers two
requests competing for the *same* version number; this one competes for different ones.
**Alternatives**
1. *Router passes the version number it validated* (the starting proposal). Right idea, but the router's own
   "latest version" read is a second read after the status read, so it has the same gap; the base must come from
   the same row that proves the status.
2. *Claim-first*: CAS `AMENDMENT_REQUESTED → DRAFT` before inserting. Serialises writers, but a double-click's
   second request then loses the claim while the first is still inserting, so it gets 409, not the idempotent
   replay D-024 promises; and the correction case (DRAFT → DRAFT) has no status change to claim.
3. *A per-document `latest_version_no` counter with CAS*: correct, but adds a new mutable field to existing
   documents (backfill/migration) for one race.
4. *Mongo multi-document transaction*: needs a replica set; docker-compose and the documented deployments run a
   standalone `mongo:7`.
5. **Chosen: derive the base from the document row the status check was made on.** In `AMENDMENT_REQUESTED` the
   base is the document's live version (`current_version_id`) — by construction nothing newer exists yet — so
   `next_version_no = base + 1` is fixed by the validated state and never re-read. A stale request then collides
   on the `(document_id, version_no)` unique index and the existing D-024 handling decides: same bytes + same
   uploader → replay (201, one version); otherwise `409 VERSION_CONFLICT`. In the correction case
   (`DRAFT` with `review_feedback`) the base is the latest version (that state can legitimately take several
   successive uploads) and, additionally, an upload identical (sha256 + uploader) to a DRAFT latest version is
   treated as a replay, since nothing distinguishes it from a double-click and a second identical DRAFT is useless.
**Other routes with check-status-then-reread (audit of `workflow.py`)**
- `review`, `approve`: read the latest version before the claim, but in `SUBMITTED` / `PENDING_APPROVAL` no upload
  can be validated, so the latest version cannot change — except for a stale in-flight upload, which the fix
  above stops at the version-number index. Not changed.
- `submit`: reads the latest version (to check its uploader) *before* claiming `DRAFT → SUBMITTED`. In the
  correction case an upload can insert a newer DRAFT in that window, so `submit` could mark the older version
  SUBMITTED while a newer DRAFT exists. Narrow (needs a correction upload racing a submit by the same people),
  not covered by the amendment fix, **reported, not fixed here**; options when picked up: re-read the latest
  version after the claim and roll the claim back on mismatch, or fold the version id into the claim filter.
- `request_amendment`, `archive`, `clear_integrity_flag`: claim/CAS only; no second read that feeds a write.
**Guardrails touched:** #7 (versions still insert-only), #11 (deterministic regression test + the existing
concurrency tests, looped).
**Not doing:** a counter field, transactions, or any change to retry/replay semantics beyond the above.

### D-032 — `submit()` verifies the version it authorised is still the latest after it wins the claim
**Problem (reported in D-029):** `submit` reads the latest version (to check the caller is its uploader), *then*
claims `DRAFT → SUBMITTED`. In the correction case a new DRAFT upload can land in between, so the document is
SUBMITTED while the version actually marked SUBMITTED (and authorised) is the older one.
**Alternatives:** (a) *fold the version id into the claim filter* — the claim is on the document row, which does not
carry the latest version id, so this needs a new field (rejected as in D-029 alt. 3); (b) *claim first, then read the
version* — the uploader check would run after the state change, so a failing check must roll back anyway;
(c) **claim, then re-read the latest version; if it is not the version that was authorised, roll the claim back
(`SUBMITTED → DRAFT`, winner only) and raise `409 ILLEGAL_TRANSITION`** — nothing else (version status, feedback,
audit) is written before the check, so the rollback restores the exact prior state; (d) a transaction (needs a
replica set; see D-029).
**Decision:** (c). The user retries and then submits the newer version, authorised against its own uploader.
**Residual, stated:** the check narrows the window to the gap between the re-read and the version-status write;
the mirror case (an in-flight upload that validated DRAFT before the claim and inserts after it) is bounded by the
same version-number index but not eliminated without multi-document atomicity. Not claimed closed.
**Guardrails touched:** #7 (no version content touched), #11 (deterministic test in the same change).

### D-030 — Starlette advisories: upgrade FastAPI 0.115.6 → 0.133.1 and pin Starlette 1.3.1
**Audit result:** `pip-audit` reports 14 rows = 7 distinct advisories (each listed twice), all in Starlette 0.41.3,
which FastAPI 0.115.6 pins (`starlette<0.47`). Severity is the OSV CVSS vector:
| Advisory | CVE | CVSS impact | Fixed in | Reachable here? |
|---|---|---|---|---|
| PYSEC-2026-1941 | CVE-2025-54121 | A:L (5.3) | 0.47.2 | **Yes, mildly** — multipart `request.form()` rolling a large upload to disk blocks the event loop (our upload route; capped at 11 MiB by D-028, so bounded, not removed) |
| PYSEC-2026-249 | CVE-2026-54283 | A:H (7.5) | 1.3.1 | **Partly** — `request.form()` limits ignored for *urlencoded* bodies. Our upload route is multipart; the geofence dependency calls `request.form()` for `application/x-www-form-urlencoded` too, but D-028's byte cap (1 MiB for non-upload routes) bounds it |
| PYSEC-2026-248 | CVE-2026-54282 | I:L (5.3) | 1.3.0 | **No in practice** — affects code that rebuilds `request.url`; we only read `request.url.path` (logging, rate limit) |
| PYSEC-2026-161 | CVE-2026-48710 | no vector | 1.0.1 | **No in practice** — Host-header-injected `request.url`; same reasoning, we never build URLs from it |
| PYSEC-2026-1942 | CVE-2025-62727 | A:H (7.5) | 0.49.1 | **No** — `FileResponse`/`StaticFiles` Range DoS; the API serves no files (downloads are pre-signed storage URLs, Guardrail #4) |
| PYSEC-2026-2280 | CVE-2026-48817 | I:L (5.3) | 1.1.0 | **No** — `HTTPEndpoint` without `methods=`; unused (FastAPI routes only) |
| PYSEC-2026-2281 | CVE-2026-48818 | C:H (7.5) | 1.1.0 | **No** — `StaticFiles` UNC path on Windows; unused |
So none is a high-impact hole in our actual paths, but two touch code we do use, and the audit is a CI gate.
**Alternatives:** (a) stay on 0.115.x/0.41–0.46 and accept/ignore advisories — fails the gate, leaves 1941/249;
(b) bump to the newest Starlette 0.x (0.49.1 clears only 1941/1942) — does not clear the rest, all fixes beyond are
1.x; (c) **FastAPI 0.133.1 + `starlette==1.3.1`** — smallest set that clears all seven: 1.3.1 is the highest fix
version; FastAPI 0.133.0 is the first release that drops `starlette<1.0`, and 0.133.1 is its patch release;
(d) latest FastAPI (0.142.x) — larger jump than needed.
**Breaking?** Starlette 0.41 → 1.3 is a **major** bump and FastAPI 0.115 → 0.133 is 18 minors of a 0.x project
(each may break); nothing in our code uses removed APIs that we know of, which is verified by the test suite below,
not assumed. The #5 middleware depends on the ASGI `receive` stream and `request.form()`, so the body-limit tests
and the full suite are re-run on the new versions.
**Guardrail tooling:** `pip-audit` is added to `backend/requirements.txt` (the project's single requirements file,
which already holds pytest/ruff) and to CI after Ruff; CI frontend job gains `npm audit --omit=dev`. Starlette is
pinned explicitly so the audit sees it and a future FastAPI bump cannot silently move it.
**Rollback:** `fastapi==0.115.6`, no Starlette pin (resolved to 0.41.3).

### D-031 — Accepted residual limits of D-028 (owner decision, 2026-10-04)
Accepted as-is: (1) JSON routes are parsed by FastAPI before their dependencies run, bounded by
`MAX_JSON_BODY_KB`; (2) `JSONLoggingMiddleware` records an aborted oversized request as 400 instead of 413;
(3) slow-body (slowloris-style) attacks are not handled in the app. (3) is recorded as a deployment-layer item
under OPS-01 in `PRODUCTION_READINESS.md` (server/proxy read timeouts, to be set when the deployment is
specified and written to `docs/DEPLOYMENT.md`).
Doc notes: one-line dated notes pointing to D-027 were added where `GeoLegalVault_Project_Plan.md` (row 32),
`IMPLEMENTATION_PROMPT.md` (lines 290, 303, 312) and `TEST_PLAN.md` (row for swapped input) say range checks catch
swapped coordinates; no text was rewritten.

### Outcome of step 2 (D-027 .. D-031)
Verified with exit codes (2026-10-04): backend `pytest` 0 (204 passed, 93.79 % coverage) on FastAPI 0.133.1 /
Starlette 1.3.1, `ruff check app tests` 0, `pip-audit -r requirements.txt --no-deps` 0 ("No known
vulnerabilities"), `pip check` 0, frontend `tsc -b` 0, `eslint .` 0, `vitest run` 0 (62 passed), `npm audit
--omit=dev --audit-level=high` 0.
**Amendment race (D-029):** `tests/integration/test_concurrency.py` (8 tests incl. the previously failing
`test_concurrent_identical_amendment_upload_is_idempotent` and two new deterministic regression tests) looped 20×
on the old Starlette: 20/20 runs passed; looped again 10× after the Starlette upgrade: 10/10. Before the fix the
same test failed 6/6 in isolation at the committed code. **Not fixed, reported:** `submit()` reads the latest
version before claiming `DRAFT → SUBMITTED` (see D-029).
**Starlette (D-030):** 7 distinct advisories, 14 audit rows; none reachable in a high-impact way, two touch code we
use (multipart/urlencoded `request.form()`), all cleared by FastAPI 0.133.1 + `starlette==1.3.1`. The #5 middleware
tests (9) and the swap-detection tests (17) pass unchanged on the new versions; a manual chunked-body check against
real uvicorn on Starlette 1.3.1 still returns 413 and stops reading at the cap. `pip-audit` is now in
`requirements.txt` and CI; CI's frontend job runs `npm audit --omit=dev --audit-level=high`.
**Limits of this verification:** pip-audit/OSV severities come from the advisories' CVSS vectors; the "reachable?"
column is my reading of our code, not a scanner result. The `starlette` 0.x → 1.x and 18-minor FastAPI jump is
exercised only by this repo's tests (no staging). CI changes (audit steps) have not been run in GitHub Actions.

### D-033 — Oversize rejection must be readable by the client: drop `Connection: close` (fixes a D-028 defect)
**Found by** the real-HTTP smoke test (`scripts/smoke_starlette_upgrade.py`), which the ASGI-level tests could not
see: when an upload exceeds the cap, the 413 is sent correctly but the client usually cannot read it — it gets a
connection reset (`WinError 10053/10054`). Cause: D-028's response carried `Connection: close`, so uvicorn closes the
socket while request bytes are still unread; closing with unread data makes the OS send a reset, which can destroy
the response the client has not yet read. A browser would report a network error instead of "file too large".
**Alternatives**
1. **Remove the `Connection: close` header** (chosen). uvicorn then keeps the connection open after the response,
   stops reading under its own back-pressure, and the client reads the 413 normally.
2. *Keep the header and drain a bounded amount of the body before responding.* Works only if the client has sent no
   more than the bound; a 15 MiB body with a 1 MiB drain still ends in a reset, and the drain delays the response and
   reads attacker bytes we just decided not to read.
3. *Respond, then keep draining in the background until the client stops or a deadline passes.* Delivers the 413
   reliably, but holds a task reading hostile data per request, which is the opposite of "abort at the cap".
**Why (1):** smallest change, no extra reading, and verified (see below). It changes no limit or status code.
**Slow-body trade-off, stated plainly (measured on uvicorn 0.34 / httptools, default settings):** after the 413 the
connection is *not* closed by us. A client that goes idle is disconnected by uvicorn's keep-alive timeout
(`timeout_keep_alive`, 5 s default). A client that keeps trickling bytes keeps the connection open — in a 20 s probe
the server stayed connected and discarded ~400 KB — so a hostile client can hold a connection slot open as long as it
keeps sending. That is the slow-body class D-031 already defers to the deployment layer (server/proxy read
timeouts); this change does not make it worse than any other slow request, but it also does not bound it. The
same-time `Connection: close` approach avoided it only by making the client unable to read our answer.
**Guardrails touched:** #5 (the rejection is now actually delivered), #11 (a real-socket test in the same change).
**Test:** `backend/tests/integration/test_body_limit_realsocket.py` starts a real uvicorn on a local port and checks
the client can read PAYLOAD_TOO_LARGE / FILE_TOO_LARGE for known-length, chunked and unauthenticated oversize
bodies, and that `/health` and a login stay prompt while a half-sent upload hangs open. It fails with the header back.
**Not doing:** draining, background tasks, changing uvicorn/gunicorn settings (deployment layer, OPS-01).
