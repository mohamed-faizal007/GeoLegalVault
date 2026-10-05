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

### D-034 — Replace MinIO with RustFS for local dev and CI (MinIO's images are gone; CI runs #16–#19 failed)
**Problem.** `docker compose up -d mongo minio minio-init` fails in CI and for anyone cloning: MinIO removed
`minio/minio` and `minio/mc` from Docker Hub, and the quay.io tags are not pullable anonymously either (real
`docker pull` of `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z` and `quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z`
both fail: `401 Unauthorized` on the manifest HEAD). `mongo:7` and `node:20-alpine` pull anonymously. What the
backend needs from storage is small and exact: private bucket, SigV4 `put/get/delete`, and **pre-signed GET URLs
that the server actually validates** (tests fetch one, and Guardrail #4 says the bucket is only reachable through
them). Production (Cloudflare R2) is not involved; this is the dev/CI stand-in only.
**Alternatives** (each candidate was pulled for real and the full backend suite — 211 tests — run against it from a
checkout with no `.env`, plus a probe for what the server does with an anonymous GET, a valid pre-signed URL, one with
a tampered signature, and an expired one)
- **(a) Mirror the saved MinIO images to `ghcr.io/<owner>/…`.** Zero code change and the exact server we tested on.
  Against: the image is frozen at 2025-09 and will never get a security fix; MinIO is AGPL-3.0, so publishing a
  public mirror makes *us* a redistributor with source-offer obligations (a private mirror breaks "anyone cloning");
  it ties every clone to a personal-account package that must stay public and alive; and it keeps an unmaintained
  object store in the CI path. **Not executed:** the `gh` token in the keyring is currently invalid
  (`gh auth status`: "token in keyring is invalid"), so it would also need `gh auth refresh -h github.com -s write:packages`
  in a browser. Not needed for the recommendation.
- **(b) A maintained S3-compatible server.** All three pulled and passed all 211 tests:
  | | image (pulled) | licence | anon GET | valid presign | tampered sig | expired | notes |
  |---|---|---|---|---|---|---|---|
  | RustFS | `rustfs/rustfs:1.0.1` | Apache-2.0 | 403 | 200 | 400 | 403 | one process, port 9000 like MinIO, has `curl` for a healthcheck; 210/211 on the first full run, see below |
  | SeaweedFS | `chrislusf/seaweedfs:latest` (v4.48) | Apache-2.0 | 403 | 200 | 403 | 403 | master+volume+filer+s3 in one container, ports 8333/9333/8080/8888; Hub has no stable version tag, so only a digest pins it; the `wget` healthcheck I tried reported unhealthy |
  | Garage | `dxflrs/garage:v2.4.1` | **AGPL-3.0** | – | – | – | – | image has no shell, so bucket/key bootstrap needs `garage layout assign/apply`, `key import`, `bucket allow` run from outside; region must be `garage`, not `auto` (`STORAGE_REGION=garage`); suite passed only after that manual bootstrap |
  (Garage's presign probe was not run; its bootstrap cost already ruled it out.)
- **(c) A mock S3 server for tests only** (`motoserver/moto:5.2.3`). 211/211 pass, **but it accepts a tampered
  signature (200) and an expired URL (200)** — it does not validate pre-signed URLs, so
  `test_download_returns_working_presigned_url` would pass against a server that cannot tell a valid URL from a forged
  one. For a project whose guarantee is "private bucket + short-lived pre-signed URL", that makes the storage tests
  vacuous. Also two code paths (mock in CI, real server in dev). Rejected.
**Chosen: (b) RustFS, pinned `rustfs/rustfs:1.0.1@sha256:1803faef…`.** It is the only candidate that is Apache-2.0,
single-process, validates signatures and expiry, runs on the same port with a one-line healthcheck, and needs no
bootstrap beyond creating a bucket. Bucket init no longer needs MinIO's `mc`: a one-shot `amazon/aws-cli:2.27.0`
(pinned by digest, Apache-2.0, on Docker Hub) runs `s3api create-bucket`; new buckets are private by default and the
result is checked below. The compose services are renamed `minio`→`storage`, `minio-init`→`storage-init`, volume
`minio_data`→`storage_data`, so nothing claims to be MinIO any more.
**Risks stated plainly.** RustFS is young (1.0.1 was published the same day this was chosen; preview builds were
shipping the day before), so it may regress or change behaviour; the digest pin means that only happens when we
choose to bump it. It is a test/dev dependency, not a security boundary. SeaweedFS is the fallback if RustFS proves
unstable (it passed with no flakes), and the S3 client code is unchanged, so swapping again is a compose-only change.
**Behaviour differences found.** (1) `ServerSideEncryption=AES256` is rejected by RustFS too (needs
`RUSTFS_SSE_S3_MASTER_KEY`), so the "we pass no SSE params" rule in `storage.py` still holds; its docstring named
MinIO and is reworded. (2) The tampered-signature status is 400 on RustFS vs 403 on MinIO/SeaweedFS; no test or code
depends on that code. (3) Container user is uid 10001; verified a fresh named volume is writable.
**Production (R2).** Unaffected: no application code path changed except a docstring/comment; R2 is selected purely by
`STORAGE_ENDPOINT`/keys/`STORAGE_REGION=auto`. What this does *not* tell us: RustFS passing says nothing extra about R2
compatibility (same limitation as with MinIO), and encryption-at-rest is still an R2 platform property.
**Guardrails touched:** #4 (private bucket, pre-signed only — re-verified on the new server: anonymous GET 403),
#2 (compose keeps `${STORAGE_*:-minioadmin}` dev defaults; no secret added). CLAUDE.md #4 wording "MinIO for local
dev" updated to name RustFS; the guardrail itself is unchanged.
**Verification (committed config, clean state).** New compose project `glv-clean-verify` (fresh `mongo_data` and
`storage_data` volumes, host ports remapped via an override file because the existing `geolegalvault` stack holds
9000/27017/8545), `docker compose up -d mongo storage storage-init` — the services CI starts: mongo and storage
healthy in <1 s after start (~7 s including container creation), `storage-init` exited 0, a second run of it (bucket
already present) exited 0, anonymous GET of an object 403 / valid pre-signed 200 / tampered 400 / expired 403. Then in a
`.env`-less checkout of the commit, in CI order: `ruff check app tests` clean; `pip-audit -r requirements.txt --no-deps`
"No known vulnerabilities found"; `pytest` with the CI env vars: **211 passed, 93.80 % coverage on Python 3.13 and
211 passed, 93.26 % on Python 3.11 (the runner's version)**. During candidate evaluation the first full RustFS run was
210/211: `test_other_requests_stay_prompt_while_a_half_sent_upload_hangs` measured 5.1 s against its `< 5 s` limit; it
passes in isolation against RustFS and MinIO alike and is dominated by `/health` probing 127.0.0.1:8545 where this
machine has a silent placeholder container (2 s probe timeout) — a timing-margin issue in that test, not a storage
difference, and it did not recur in the two full runs above.
**Not verified:** a GitHub Actions run (nothing pushed); the `docker compose` default project name
`geolegalvault` on the runner (CI's container-name waits assume the checkout directory is named `geolegalvault`
case-insensitively, as before this change); Docker Hub anonymous pull rate limits on shared runners (3 images:
mongo, rustfs, aws-cli).

### D-035 — CI MIME_MISMATCH: fix the test filler, not the MIME check
**Problem.** CI run on def8025: `test_upload_exactly_at_the_file_size_limit_still_works` got 422 `MIME_MISMATCH`.
The test uploaded 10 MiB of one repeated byte (`b"a" * MAX_FILE`) claiming `text/plain`; the runner's libmagic
(apt `libmagic1` on Ubuntu) detected `application/SIMH-tape-data`, while the libmagic bundled with `python-magic-bin`
on the dev machine calls it text. A single repeated byte is not text in any meaningful sense, so libmagic's answer on
it is version-dependent. The product behaviour (reject content that does not match its claimed type) is correct.
**Alternatives**
1. **Make the filler genuine ASCII text** (chosen): repeated lines of `GeoLegalVault size-limit filler line\n`, cut to
   exactly the wanted size. Keeps `text/plain`, the exact-boundary size and the SHA-256 assertion.
2. A minimal real PDF header plus padding. Stable (libmagic keys on `%PDF-`) but odd for a `text/plain` test.
3. Loosen/skip MIME validation in the test or add `SIMH-tape-data` to the accepted set. Rejected: it weakens
   Guardrail-level validation to make a test pass.
**Change.** Test-only: helper `_text_filler()` in `tests/integration/test_body_limit.py`, used by the exact-limit test
and the one-byte-over test. No application code touched.
**Fragility audit of other synthetic filler.**
- One-byte-over test (`test_body_limit.py`): same filler, switched. It never reaches libmagic anyway: the size check
  (`documents/service.py:101-102`) runs before `magic.from_buffer` (line 108), so it gets FILE_TOO_LARGE regardless.
- `test_body_limit.py` streaming `b"x"` bodies and `test_body_limit_realsocket.py` `b"a"` bodies: all are aborted at the
  byte cap, answered 401, over the file-size rule (FILE_TOO_LARGE, before libmagic), or never completed (half-sent
  upload). None reaches libmagic; left unchanged.
- `PDF_BYTES` (`%PDF-1.4\n…` + `A*200`) in test_upload / test_security_cases / test_workflow / test_concurrency:
  libmagic identifies PDF from the `%PDF-` header; not expected to vary, left unchanged. Residual risk, not proven.
- `test_upload.py` `MZ…` as `application/x-msdownload`: rejected as unsupported type before libmagic.
**Verification, stated plainly.** The runner's libmagic cannot be reproduced locally, so a local pass proves only that
the new filler is accepted by the bundled libmagic. **CI is the real verification** and has not yet run on this fix.

### D-036 — Pin CI runners to `ubuntu-24.04` instead of `ubuntu-latest`
**Problem.** `ubuntu-latest` is scheduled to move to Ubuntu 26 on 2026-10-19. The runner image supplies `libmagic1`
(the CI MIME_MISMATCH in D-035 was a libmagic version difference), Docker, and the toolchain, so a silent image
change can alter MIME detection or compose behaviour with no commit on our side to blame.
**Alternatives**
1. **Pin all three jobs to `ubuntu-24.04`** (chosen): the image stays fixed until we choose to move.
2. Keep `ubuntu-latest` and fix breakage as it appears. Rejected: the failure would arrive on an unrelated commit.
3. Pin to `ubuntu-22.04`. Rejected: older than needed, nearer to end of life.
**Change.** `.github/workflows/ci.yml`: `runs-on: ubuntu-latest` → `ubuntu-24.04` in all three jobs (`backend`, `contracts`, `frontend`).
No application code touched.
**Cost / follow-up.** A pinned image must be bumped by hand before GitHub retires it; moving to Ubuntu 26 should be a
deliberate change that re-runs the suite.
**Verification.** Not verifiable locally; CI on this commit is the check, and nothing is pushed.

## 2026-10-04 — REL-01: anchoring must not leave documents stuck

Context: PRODUCTION_READINESS.md REL-01 (R13). Backend stage first (worker, API, permissions, tests); UI and the
CLAUDE.md notes follow as a second stage with their own decisions.

### D-037 — REL-01 root cause, evidence, alternatives, and the chosen design (A: retry inside the one worker)
**Evidence (read-only queries on the dev DB, re-run 2026-10-04).** 22 anchor rows: 19 CONFIRMED, 3 FAILED, 0 PENDING.
The 3 FAILED rows are one approval's three in-request attempts (1 s apart, `ANCHOR_MAX_ATTEMPTS=3`) on "Approval Demo"
v1 on 2026-08-29, error text `SEPOLIA_RPC_URL is not configured` (written before D-020, so raw text, not a code). The
document is APPROVED with `anchor_pending_alert=true`, its version is APPROVED with no `anchor_id`, and the contract
holds nothing for it (`getAnchor` returns `exists: false`). Re-approving returns 409. **Its stored object does not
exist**: `head_object` returns 404 (so do 4 other versions in dev; one of those is an ACTIVE version, not part of this
item). All 22 anchor rows lack the `live` field (D-023: legacy rows sit outside the partial unique index).

**Defects in the code.**
1. `confirm_pending_anchors` selects `status == PENDING` only: a FAILED anchor, or an APPROVED document with *no*
   anchor row at all, is never revisited. A PENDING row whose tx was dropped is polled forever.
2. `run_forever` has no `try/except`; `confirm_tx` raises on an RPC error mid-loop, so one outage ends the worker.
3. The worker is not in the Dockerfile or `docker-compose.yml`.
4. `anchor_pending_alert` is written but never read by any API or the UI.
5. A crash between `send_raw_transaction` and the row insert leaves a mined tx with no row.
6. (Found while designing) `promote_confirmed_anchor` claims PENDING to CONFIRMED and then performs several writes; a
   crash in between leaves a CONFIRMED anchor under an APPROVED document, which nothing resumes.

**Alternatives.** (A) retry inside the one worker with a reconcile loop and backoff **(chosen, owner-approved)**;
(B) a scheduled/cron job calling the same function: a second deploy component with minute granularity and no
heartbeat, i.e. a worse worker; (C) on-demand retry only: documents stay stuck until a human notices, kept only as a
supplement (the admin re-queue, D-041); (D) longer retries inside `approve()`: blocks the HTTP request and does not
survive a restart.

**Design.**
- **State lives on the document**: `documents.anchor_retry = {attempts, next_attempt_at, lease_owner, lease_until,
  last_error, permanent, permanent_reason, queued_at, requeued_by, requeued_at}`. `blockchain_anchors` stays an
  append-only log (one row per tx sent or adopted). `document_versions` is not touched (Guardrail #7).
- **Eligible work:** a document in `APPROVED` whose latest version is `APPROVED`. The worker never moves a document
  out of any other state.
- **Idempotency order (every attempt, under the lease):**
  1. *An existing anchor for this version?* Look at rows by `version_id` and **`status`** (`PENDING`/`CONFIRMED`),
     not by `live`. That is how legacy rows are covered without a backfill: the partial unique index protects only
     rows that carry `live: true`, but this check does not depend on it. A PENDING row is left to the confirm pass
     (and declared `TX_DROPPED` once older than `ANCHOR_PENDING_TIMEOUT_SEC` with no receipt). A CONFIRMED row under
     an APPROVED document means an interrupted promotion (defect 6): finish it, send nothing.
  2. *Does the chain already hold it?* `getAnchor(document_id, version_no)`. Same hash: **adopt**. Insert a CONFIRMED
     row (`adopted: true`, no `tx_hash`; the key is simply absent, so the sparse unique index is unaffected, and the
     contract's event does not index `documentId`, so recovering the original tx hash would mean scanning logs) and
     promote. A *different* hash for that pair: permanent `ALREADY_ANCHORED`, alert, audit. The contract can never
     accept a second anchor for the pair, so retrying cannot succeed.
  3. *Is the stored object there?* (D-039).
  4. Only then send, via the existing `anchor_document_version`, which records a PENDING or FAILED row.
- **Layers that stop a duplicate, strongest first:** the contract itself (`already anchored` revert; the only guard
  that holds across processes and crashes), the Mongo lease (one worker per document at a time), the partial unique
  index (new rows), and the status-based check in step 1 (legacy rows).
- **Residual, stated:** a crash between send and row insert (defect 5) can at worst waste one reverted tx on the next
  attempt (the contract rejects the duplicate); it can never produce a second anchor. The next attempt's `getAnchor`
  adopts the mined one if it has landed.
- **Nonce:** `_send_lock` is per process, and the API (at `approve()`) and the worker both sign with the one service
  wallet. A cross-process nonce collision surfaces as a send error, is classified `ANCHOR_FAILED`/`RPC_UNREACHABLE`,
  and is retried like any transient failure; the race test uses two real processes to prove it heals.

**Guardrails:** #1 (only `{documentId, version, sha256, eventType}`; the hash is read from the DB version row), #3
(D-041), #7 (no write to `document_versions`; promotion uses the existing whitelisted helpers), #10 (the one optional
worker; no queue, no broker), #11 (tests with the change).

### D-038 — Retry policy, error codes, and the lease numbers
**New codes** (additive to `KNOWN_ERROR_CODES`, so `public_error` passes them through): `TX_DROPPED` (a PENDING tx
that never produced a receipt within the timeout), `RETRIES_EXHAUSTED` (transient attempts used up),
`STORED_OBJECT_MISSING` (D-039). `ALREADY_ANCHORED` is reused for "chain holds a different hash".
**Policy by class** (the code comes from `classify_anchor_error`; stored, logged and returned values are codes only,
per D-020):

| Code | Retry | Backoff (n = failures so far) | Ends as |
|---|---|---|---|
| `RPC_UNREACHABLE`, `ANCHOR_FAILED`, `TX_DROPPED` | up to 8 | `min(900, 30*2^(n-1))` s: 30, 60, 120, 240, 480, 900, 900 | permanent `RETRIES_EXHAUSTED` after the 8th failure (about 45 min of trying) |
| `INSUFFICIENT_FUNDS` | up to 8 | `min(3600, 600*2^(n-1))` s: 600, 1200, 2400, 3600, ... (about 4.4 h) | permanent `RETRIES_EXHAUSTED`; **its own alert** (the attention item shows `last_error=INSUFFICIENT_FUNDS`) so ops can fund the wallet and an admin can re-queue |
| `REVERTED` | 2 | base schedule | permanent `REVERTED` |
| `NOT_AUTHORIZED`, `NOT_CONFIGURED` | none | n/a | permanent immediately (retrying cannot fix a missing writer role or config) |
| `ALREADY_ANCHORED`, different on-chain hash | none | n/a | permanent immediately |
| `STORED_OBJECT_MISSING` | none | n/a | permanent immediately |

Every number is a setting (`ANCHOR_RETRY_*`, documented in `.env.example`) so tests can shrink them to milliseconds.

**Lease numbers.** `ANCHOR_PENDING_TIMEOUT_SEC = 600` (a tx with no receipt for 10 min is declared `TX_DROPPED`; a
Sepolia block is about 12 s, so this is about 50 blocks) and `ANCHOR_LEASE_SEC = 900`. The lease is deliberately
**longer than the confirmation timeout** (900 > 600, 300 s of margin for a slow RPC): a live holder can never be
preempted while still inside a send-and-confirm window, and a crashed worker's document is picked up again after at
most 15 min. A lease is taken by compare-and-swap (`find_one_and_update` on `lease_until` absent or expired), is
released when the attempt ends, and is never extended. `anchor_pending_alert` keeps its meaning (set on failure,
cleared on promotion).

**Audit.** Individual failed attempts are not audited (each is already a `blockchain_anchors` row and a redacted log
line). Audited: `ANCHOR_ADOPTED`, `ANCHOR_OK` (existing), `ANCHOR_PERMANENT_FAIL` (with the code),
`ANCHOR_RETRY_REQUESTED`. The in-request attempts inside `approve()` are unchanged and are not counted in the 8; after
they fail, `approve()` enqueues the document (`anchor_retry`) so the worker takes over.

### D-039 — Pre-send check that the version's stored object exists
**Question.** Should the worker refuse to anchor a hash whose file is not in storage? (Approval Demo's object is a
404.) **Weighed.** An anchor is permanent and one per (document, version): anchoring a hash for a file that cannot be
retrieved writes an immutable on-chain record that can only ever verify as an integrity failure, and it permanently
uses up that pair. Cost of the check: one `HEAD` per attempt, no body read. Risk: a *storage outage* must not be
mistaken for a missing file. **Decision: do it, in the worker's retry path only.** Only an authoritative
404/NoSuchKey is permanent (`STORED_OBJECT_MISSING`); any other storage error is transient and retried under the
normal backoff. It checks *existence*, not integrity (re-hashing needs the whole object; `verify` already does that
after the fact). The first in-request attempt inside `approve()` is left as is: changing it would change approve
latency and its existing tests for a case the upload path makes rare. New helper `storage.object_exists(key)`, run
with `asyncio.to_thread` because boto3 is synchronous (REL-05).
**Consequence for the dev data.** Approval Demo is both older than the auto-retry age cutoff (D-040) and missing its
object, so even an admin re-queue would end as permanent `STORED_OBJECT_MISSING` rather than spending gas.

### D-040 — The worker: loop, heartbeat, health, compose, auto-retry age cutoff, dry-run
- **Loop** (`python -m app.workers.anchor_confirmer`): each pass is wrapped in `try/except Exception`; an error is
  logged redacted, recorded in the heartbeat as a code, and the loop sleeps and continues. Per-document work is
  isolated too, so one bad document does not stop the pass. `CancelledError` propagates for a clean stop. A pass does,
  in order: (1) confirm PENDING anchors (also detects `TX_DROPPED`), (2) reconcile eligible APPROVED documents
  (D-037). `--once` runs a single pass (used by the race test); `--healthcheck` exits 0/1 from heartbeat age;
  `--dry-run` is below.
- **Heartbeat**: one document in `worker_heartbeats` (`_id: "anchor_worker"`) updated every loop: `last_beat_at`,
  `last_ok_at`, `last_error_code`, `passes`. Stale means no beat for `ANCHOR_WORKER_STALE_SEC` (120 s, 8 loop
  intervals of 15 s). It is a plain collection in the same database, not a new service (#10).
- **`/health`** gains one key, `anchor_worker: "ok" | "stale"`, a bare flag with no detail (the endpoint is
  unauthenticated, SEC-17). It does **not** change the overall `status`: the worker is optional (#10), so a dev stack
  without it must not read as degraded. Never having run reads as `stale`.
- **Compose**: service `anchor-worker`, same image, command `python -m app.workers.anchor_confirmer`, healthcheck
  `... --healthcheck`, behind the **opt-in profile `worker`**
  (`docker compose --profile worker up -d anchor-worker`). Nothing in CI names it, and CI's
  `docker compose up -d mongo storage storage-init` does not start profiled services.
- **Auto-retry age cutoff** `ANCHOR_AUTO_RETRY_MAX_AGE_DAYS = 7`. The worker only *sends* for documents whose
  `queued_at` is within the cutoff; older stuck documents are listed as `NEEDS_ADMIN_RETRY` and never auto-sent.
  `queued_at` is set at enqueue; for documents with no `anchor_retry` (legacy or crash) it is taken from the earliest
  anchor row for the version, else the document's `updated_at`. An admin re-queue (D-041) resets `queued_at`, which is
  what makes it a deliberate act. **Why:** the dev DB points at public Sepolia, so a worker's first start must not
  spend testnet gas on months-old demo rows.
- **`--dry-run`**: no writes, no sends. It lists every document the worker would consider and, for each, the action
  it would take (`would NOT send: needs admin retry`, `would adopt`, `would send 1 tx`, `would mark permanent
  STORED_OBJECT_MISSING`, ...). It performs read-only checks (a `getAnchor` `eth_call` and a `HEAD`) so the plan is
  accurate; it never builds or signs a transaction. The owner reviews that output before the worker is ever started
  against the dev DB, and this work does not start the worker against the dev DB.

### D-041 — API, permissions, the manual re-queue, and Guardrail #3
- `GET /api/v1/blockchain/anchors/attention`: new permission **`anchor:view`** (Administrator, Legal Officer,
  Auditor). Lists documents that are APPROVED and either flagged, in retry, permanent, awaiting confirmation too long,
  or older than `ANCHOR_ATTENTION_GRACE_SEC` (120 s): `document_id`, `title`, `version_no`, `state`
  (`RETRYING | AWAITING_CONFIRMATION | PERMANENT_FAILURE | NEEDS_ADMIN_RETRY`), `last_error` (a code, via
  `public_error`), `attempts`, `next_attempt_at`, `stuck_since`, `can_retry`. No hash, key, URL or tx internals.
- `POST /api/v1/blockchain/anchors/{document_id}/retry`: new permission **`anchor:retry`** (Administrator only).
  Body `{reason}` (10-1000 chars, required). Pipeline in the documented order: JWT, RBAC, geofence, validation,
  action, audit; **the admin therefore needs an assigned geofence** (new context `anchor_retry`). It **only
  re-queues**: a compare-and-swap on a document that is APPROVED, not currently leased, and has no PENDING or
  CONFIRMED anchor resets `anchor_retry` to `attempts=0, permanent=false, next_attempt_at=now, queued_at=now`; `409`
  otherwise. It never contacts the chain and never signs; the worker does. The hash always comes from the DB version
  row; nothing in the request names a hash, version, tx or address. Audit: `ANCHOR_RETRY_REQUESTED` with the reason.
- **Guardrail #3 is not amended.** The reading recorded in CLAUDE.md: a user may *request a re-drive* of an anchor
  the system already owes; they never sign and never choose what is anchored. Only one clarifying sentence is added
  to #3.
- Not doing: adding anchor state to `DocumentOut` (not required; the attention endpoint carries it); a retry for a
  document that is not APPROVED; any bulk retry.

### D-042 — Test plan (tests written first, shown failing on the current code)
No `pytest-timeout` in the repo and none is added; each new test enforces a **hard timeout itself**
(`asyncio.wait_for` around the body, `timeout=` on every subprocess), and Hardhat start-up uses the existing
`HARDHAT_START_TIMEOUT_SEC` (D-021; default 90 s, the slowest observed CI cold start was 47 s) through a node-control
fixture that polls readiness and never sleeps a fixed time. Cases, each on a real local Hardhat node:
1. **Node killed and restarted**: approve with the node down, a worker pass while it is down (must not raise),
   restart, the next pass anchors. And a tx that was PENDING when the node was killed (manual mining) is lost by the
   restart, declared `TX_DROPPED`, and re-sent.
2. **Transient RPC failure**, with an error whose text carries a fake API-keyed URL (no key may reach a row, a log
   line or the API).
3. **Permanent failure** (the service wallet is not a writer, so `NOT_AUTHORIZED`): no further attempts, alert,
   attention item.
4. **Two workers racing**, both in-process and as two real OS processes.

Plus: adopt, different-hash, missing-object, legacy row without `live`, age cutoff, interrupted promotion, admin
re-queue, RBAC matrix, heartbeat and `/health`. A "fails without the fix" run against the unmodified code is shown to
the owner before any implementation.

### D-038 (addendum, before implementation) — `TX_DROPPED` needs the node to have forgotten the tx
Found while writing the tests: "no receipt after `ANCHOR_PENDING_TIMEOUT_SEC`" is not by itself proof the tx was
dropped. On a congested chain a tx can sit in the node's mempool for longer than the timeout; declaring it dropped and
re-sending would put a second tx for the same (document, version) in flight (the contract would revert the loser and
waste its gas, though never create a second anchor). **Rule:** a PENDING anchor is declared `TX_DROPPED` only when it is
older than the timeout, `eth_getTransactionReceipt` has nothing, **and** `eth_getTransactionByHash` returns nothing
(the node no longer knows the tx — a restart, reorg or testnet reset). If the node is unreachable the check is skipped,
never treated as "dropped". A tx the node still holds is left waiting, however old; the age is then visible to
operators through `stuck_since` and the `AWAITING_CONFIRMATION` state. New helper `chain.tx_known(tx_hash)`.
Tests: `test_young_or_mempool_pending_tx_is_never_resent` (manual-mining node, row older than the timeout, legacy row
without `live`, wallet nonce must not move) and `test_tx_lost_when_node_is_killed_mid_anchor_is_dropped_and_resent`.

### D-043 — Implementation details that go beyond D-037..D-042 (recorded as they were decided)
- **Coverage exclusion removed.** `pyproject.toml` omitted `app/workers/*` from the coverage gate on the grounds
  that the worker was the first thing the project's cut-list says may go untested. REL-01 makes it the recovery path
  for failed anchors, so the exclusion is deleted (Guardrail #11) and `docs/TEST_PLAN.md` is updated to say what is
  and is not covered.
- **Heartbeat fields.** `last_error_code` is the *most recent* error and stays visible after a clean loop, with
  `last_error_at`; `last_ok_at` is stamped by clean loops. (D-040 said `last_error_code`; the timestamp is added so an
  operator can tell a stale error from a current one.)
- **Re-queue refusal code.** `409 ANCHOR_NOT_RETRYABLE` for: document not APPROVED, an anchor already PENDING or
  CONFIRMED for the latest version, or the document leased by a live worker. Unknown or malformed ids are `404`. A
  missing location on the retry request is `422 InvalidLocation`, like every other geofenced endpoint here.
- **What `attempts` counts.** Failed *worker* attempts (and dropped/reverted txs found by the confirm pass). The
  in-request attempts inside `approve()` are not counted (D-038). A successful send is not a failure, so a document
  that sends and then has its tx dropped counts one attempt per drop.
- **Enqueue decides "permanent now" immediately.** When `approve()`'s own attempts fail with `NOT_AUTHORIZED` or
  `NOT_CONFIGURED`, `anchor_retry.permanent` is set at once and `ANCHOR_PERMANENT_FAIL` is audited, so an admin sees it
  without waiting a worker pass. `ALREADY_ANCHORED` at that point is *not* permanent: the worker's chain read decides
  between adopt and permanent. It is still bounded (`ANCHOR_RETRY_MAX_ATTEMPTS`) so it cannot loop.
- **Reverted/dropped detection uses a compare-and-swap** (`fail_pending`: PENDING to FAILED only if still PENDING), so
  `approve()` and a worker pass that both see the same reverted receipt count it once.
- **No confirm wait inside a worker attempt.** After sending, the attempt records the PENDING row and returns; the
  next loop's confirm pass promotes it (up to `ANCHOR_WORKER_INTERVAL_SEC` = 15 s later). This keeps the lease
  short in practice; it is still configured longer than the confirmation timeout (D-038) as the safe upper bound.
- **Terminal state is cleared.** On promotion `anchor_retry` is removed from the document; history stays in the anchor
  rows and the audit log.
- **Attention list bound.** At most 500 APPROVED documents are scanned per request (a stuck document is by
  definition APPROVED, and APPROVED is a state a healthy document leaves within seconds).

### Outcome of REL-01, stage 1 (backend: D-037..D-043)
**Verified with exit codes (final tree):** backend `pytest` 0 (**268 passed**, 93.76 % coverage, gate 60 %),
`ruff check app tests` 0, `pip-audit -r requirements.txt --no-deps` 0 (no known vulnerabilities; no dependency
changed). Frontend is untouched in this stage.
**Tests fail without the fix.** The new suite was run against the unmodified application code first (only test files
existed): **43 failed, 1 error (the policy module did not exist), 1 passed**, in 342 s, with no hang (every body has its
own hard timeout). Reasons, by test: FAILED anchors never retried (`anchor_retry` absent); a worker pass **raised
`ConnectionError`** with the node killed; `run_forever` **died** on the first RPC error; documents stayed APPROVED for
the whole 25 s polling window in the adopt, different-hash, interrupted-promotion, missing-object and bounded-retry
cases; the old `__main__` ignores `--once` and loops, so the two-process race hit its 60 s timeout; the API and
`/health` additions were 404 / missing. The one test that passed on the old code
(`test_young_or_mempool_pending_tx_is_never_resent`) is a guard for the *new* worker, which the old worker could not
violate. After the fix: 15 + 2 reliability tests, the API, ops and unit tests all pass.
**Mutation check (the red run above only proves "fails when the feature is missing").** Each safety mechanism was
broken in turn, its test run, and the file restored byte-for-byte (md5 verified): lease not exclusive, caught by
`test_two_workers_in_one_process_send_exactly_one_tx`; never reading the chain, caught by the adopt test; judging
"anchor exists" by `live` instead of status, caught by the legacy-row mempool test; unbounded attempts, caught by the
bounded-retries test; skipping the stored-object check, caught by the missing-object test; **declaring `TX_DROPPED` on
age alone was NOT caught at first**: the test ran its passes back to back, inside the 50 ms backoff, so the re-send
never happened in the window. The test was fixed (passes spread over 0.8 s, and it now also asserts the row is still
PENDING) and the mutation is caught.
**What prevents a duplicate anchor, stated plainly.** The contract's `already anchored` revert is what prevents a
duplicate anchor across processes (and across crashes and hosts): no second anchor for a (document, version) can ever
exist on chain, whatever the application does. The **lease does not provide that guarantee; it only avoids wasted
work** (a second worker sending a tx that would just revert and burn gas, and a spurious FAILED row). The partial unique
index and the status-based check protect the *database* from a duplicate live row, not the chain. Consequently the
tests split the same way: the in-process test is the one sensitive to the lease (it counts sends, which is the wasted
work); the two-OS-process test proves the end state across processes (one CONFIRMED row, one on-chain anchor, at most
one `live` row, a loser's nonce collision heals) and **would still pass with the lease removed**, because the contract
is the guard. Both run on one machine; a cross-host race is not exercised.
**Tests added in the same change (Guardrail #11):** exact-map RBAC test, role x endpoint matrix and `/health` shape
updated; reverted-receipt paths in `approve()` and in the worker (found uncovered by the coverage report and then
tested).
**Dev data (read-only, nothing sent, worker not started against it).** `--dry-run` on the dev DB: 1 APPROVED
document, "Approval Demo" v1, `NEEDS_ADMIN_RETRY` (36.0 days), chain `ABSENT`, stored object `MISSING`, **0
transactions would be sent**; a fingerprint of every collection was identical before and after. An admin re-queue of
that document would end as permanent `STORED_OBJECT_MISSING`, not a transaction. Separately noted, out of scope: 4
other dev versions also have no stored object. All 5 (Approval Demo above, and "Manual Verify NDA", "Test Contract",
"Lifecycle Test" and "Anchor Demo", all created 2026-08-29 with old-format `docs/{id}/v1` keys) were checked against the
old MinIO volume `geolegalvault_minio_data` (read-only mount): none of their objects is in it, while a control
document is. **So they were already broken before the RustFS switch (D-034), not caused by it.** The one with an
ACTIVE version is "Anchor Demo" (document `6a92dcc06aa1882bd4c46f8a`, document status ARCHIVED, version
`6a92dcc06aa1882bd4c46f8b`, anchored); it will verify as unreachable/mismatch until its file is restored, which is
outside REL-01.
**Not verified:** a GitHub Actions run (nothing pushed; CI must start no worker, which the opt-in compose profile
guarantees by construction: `docker compose config --services` lists no `anchor-worker` without `--profile worker`); a
real Sepolia run; running the compose worker container itself (compose file validated with `docker compose config`
only). The UI alert and the CLAUDE.md #10 notes are stage 2.

### D-044 — REL-01 stage 2: the Dashboard alert and the Administrator retry (logged after the code was written, which is the wrong order; the decisions themselves were made before the tests)
- **Where and who.** A banner at the top of the Dashboard (`components/AnchorAttentionBanner.tsx`), rendered only for roles
  with `anchor:view` (Administrator, Legal Officer, Auditor; the client map in `lib/permissions.ts` mirrors the backend, UX
  only). For other roles it renders nothing and **does not call the API**. It renders nothing when no document needs
  attention, so a healthy vault shows no banner. It polls every 30 s.
- **State in words, not colour.** Each row shows the state as a `StatusBadge` whose text is the state (`RETRYING`,
  `AWAITING CONFIRMATION`, `PERMANENT FAILURE`, `NEEDS ADMIN RETRY`) plus a sentence saying what is happening and who has
  to act ("An administrator needs to request a retry" for roles that cannot). Tones in `lib/status.ts` only help scanning.
- **No raw error text, no RPC details.** The backend already sends only a fixed code (D-020, D-041). The UI additionally maps
  *known* codes to a sentence and prints the code in brackets, and an **unrecognised value becomes a generic sentence and is
  never echoed** (`lib/anchorAttention.ts`), so a future backend change cannot put an RPC URL on screen. Tests assert a
  leaky string never reaches the DOM.
- **Retry (Administrator only).** Button "Retry anchoring" per row, shown only if the role has `anchor:retry` **and** the
  server says `can_retry` **and** the state is not `AWAITING_CONFIRMATION` (the server refuses that too). It opens an inline
  form (same pattern as "Clear integrity flag"): a reason textarea, at least 10 characters (the server's rule), a note that
  this only re-queues and the reason is audited (no personal data). Submitting reads the browser location and sends it as
  `X-Geo-*` headers like Approve (the endpoint is geofenced, so the admin needs an assigned geofence; a denial shows through
  the existing `ErrorBanner`). On success the list is refetched and a status message confirms the request.
- **Honesty about the worker.** A retry only re-queues; if no worker runs, nothing happens. While the banner has items it
  reads the unauthenticated `/health` (`anchor_worker`) and, if `stale`, says so plainly. It is a hint, not a guarantee.
- **Reuse.** `StatusBadge`, `ErrorBanner`, the `card`/`card-header`/`btn-*`/`input` classes, `formatDateTime`, `geoHeaders`
  and `getCurrentLocation`. No new dependency, no change to `DocumentOut`.
- **Error text.** `ANCHOR_NOT_RETRYABLE` gets a plain-language message in `lib/errorMessages.ts`.
- **Not doing:** a per-document banner on the details page, notifications (FUN-01), editing the stored file, bulk retry.
- **Tests.** `components/__tests__/AnchorAttentionBanner.test.tsx` (per role, per state, no leakage, retry flow, refusal,
  location failure, worker hint), `pages/__tests__/DashboardAnchorAlert.test.tsx` (placement), `lib/__tests__/
  anchorAttention.test.ts` (text mapping and the permission mirror). The Dashboard test waits up to 8 s per query: a first
  version used the 1 s default and failed once under full-suite load.

### Outcome of REL-01, stage 2 (UI: D-044)
**Verified with exit codes.** Frontend `tsc -b` 0, `eslint .` 0, `vitest run` 0 (**92 passed**, 15 files; run twice in a row
after a timing fix, see D-044). Backend `ruff check app tests` 0. Backend `pytest`: **267 passed, 1 failed, exit 1**, coverage
93.80 %. The one failure is `tests/integration/test_body_limit_realsocket.py::
test_other_requests_stay_prompt_while_a_half_sent_upload_hangs` (hard limit `< 5 s`; measured 5.4 s in the full run, and
5.7-6.3 s in three isolated runs). **It is not caused by REL-01:** the same test, run in a temporary worktree at the commit
before any REL-01 work (`4fec3f8`, with the repo's `.env` copied in and removed afterwards), fails the same way, 5.5-5.9 s on
three of three runs. The new `/health` heartbeat read measures 0.00 s. D-034 had recorded this test as timing-marginal
(5.1 s once, passing in isolation); on this machine today it is consistently over the limit, with ~1.5 GB RAM free. It passed
in the Stage 1 full runs (268 passed). It is a property of the test's margin and this machine's current load, not of the code
under test; it is left unchanged here and flagged for a decision on how to make it robust (see D-021's reasoning against just
raising a timeout).
**Not verified:** a GitHub Actions run (nothing pushed); the banner in a real browser (the component is covered by
jsdom tests only, so layout and the 30 s polling were not seen on screen); the admin retry end to end against a running
worker (the API half is tested against the real backend with a mocked client on the frontend side).

## 2026-10-05 — Test robustness follow-up

### D-045 — `test_other_requests_stay_prompt_while_a_half_sent_upload_hangs`: measure against this machine's own baseline, not a fixed 5 s
**Problem.** The test opens a connection that sends a valid upload header and a little body, then stalls, and asserts that
`GET /health` plus `POST /auth/login` finish in `< 5 s` while it hangs. It now fails every time on the owner's machine:
5.4 s in a full run, 5.7-6.3 s in three isolated runs, and **5.5-5.9 s on three of three runs at `4fec3f8`**, the commit before
any REL-01 work, so it is not caused by that work. D-034 had already seen 5.1 s once. The stalled upload is not what is slow:
`/health` makes two outbound HTTP probes and each one builds an SSL context (about 1 s of CPU on this machine, D-021), and
login hashes a password, so the two requests cost a few seconds of this machine's CPU with or without any upload. The
absolute number encodes machine speed; the test is meant to detect something else: **the server being tied up by the
stalled upload so that other requests do not complete until it ends**.
**Alternatives**
- **(a) Compare with a baseline latency measured in the same test.** Run the same two requests twice before the stalled
  connection is opened, keep the slower, and require the during-hang time to be `<= max(3 x baseline, baseline + 3 s)`.
  The bound follows the machine and the current load, and the failure message carries both numbers.
- **(b) A much looser absolute bound** justified by the failure mode (a block lasts as long as the stalled upload, which
  has no read timeout here, so it is unbounded). Catches the real failure on any machine, but it hard-codes a speed
  assumption in the other direction: too tight on a slower runner, too loose to notice partial blocking on a fast one.
- **(c) Retry once.** Does not touch the cause: a machine that is over the limit is over it every time (3 of 3 here), so
  this only doubles the runtime of a test that fails anyway, and teaches people to re-run and ignore it.
- **(d) Raise the timeout.** D-021 argued against this: a longer fixed limit only hides contention and delays the report of
  a real hang. It would also just move the number the next slow machine exceeds.
**Recommendation and decision: (a), with (b)'s idea as its backstop.** The probe requests get a 20 s client timeout, so a
server that is actually blocked is reported as a clear failure ("blocked by a half-sent upload") after at most 20 s instead of
hanging, and the ratio check does the proportional work. Using the slower of two baseline runs and a `3x + 3 s` margin keeps
a noisy neighbour from tripping it. **Stated limit:** a block shorter than that margin is not detected. That is intended: the
guard is against the unbounded kind of block (the stalled upload holding the worker), not against small slowdowns. Test-only
change; no application code is touched.
**How it is checked (shown to the owner).** (1) A mutation: a synchronous 25 s sleep inserted before `await request.form()` in
`upload_document` (standing in for a handler that blocks the worker for as long as a stalled upload would; the file is
restored byte-for-byte, md5 verified) must make the test FAIL within a hard outer timeout. (2) The fixed test must PASS while
the machine is loaded with CPU burners, and the old absolute-bound version of the test is run under the same load for
contrast.
**Outcome of D-045 (test-only change; no application code touched).**
- **Unloaded:** the fixed test passes 3 of 3 (7.6 s, 7.9 s, and once 30.9 s when the machine happened to be busy, which the
  ratio absorbed), and the whole `test_body_limit_realsocket.py` file passes (6 tests).
- **Mutation, RED as required.** A synchronous sleep before `await request.form()` in `upload_document` (restored
  byte-for-byte, md5 verified, `git status` clean afterwards), under a hard outer timeout: the test fails with
  "other requests did not complete within 38s while a half-sent upload was open (baseline without it: 9.2s): the server is
  blocked by the stalled upload", in about 65-80 s. A first attempt with a 25 s sleep also failed, but it exposed a
  property worth stating: **a finite block shorter than the margin is not detected** (on a machine whose baseline is 17 s, a
  25 s block is inside `3 x baseline`). That is the limit stated above, so the mutation uses a 600 s sleep, i.e. the unbounded
  block the stalled upload would cause. The probe timeout also now scales with the baseline (`max(20, 3 x baseline + 10)`)
  because the first design's fixed 20 s was tight when the baseline itself reached 17 s.
- **Under load.** With CPU burners on 6 of the 12 logical CPUs: the **new test passes** (173 s wall, the machine being slow),
  and the **old fixed-5 s test fails** under the same load (105 s). A first experiment that saturated all 12 CPUs was a bad
  experiment (everything crawled: the old test took 251 s to fail and the new one hit my 300 s outer guard) and is
  **inconclusive**; no claim is made from it.
- **Cost:** under heavy load this test can take minutes, because each baseline probe may wait up to 60 s. It only waits that
  long when the machine is that slow.

### D-046 — Two timing failures found by the full-suite run after D-045 (one mine, fixed; one older, characterised and left)
The full suite after D-045 ran 12 minutes (a loaded machine; earlier full runs took about 3) and failed two tests.
**1. `test_transient_failures_back_off_then_succeed_without_leaking_secrets` (mine, fixed).** It asserted that a worker pass
run *immediately* after a failed attempt does not retry "because it is inside the backoff window". In the fast test settings
that window is 50 ms, and on a slow machine the next pass legitimately arrived after it, so the worker was right and the test
was wrong. This is the fragile kind of assertion ("nothing may happen within a short real-time window"). Fixed by saying what
is meant instead of racing the clock: the test sets `next_attempt_at` explicitly (60 s ahead: the worker must leave it alone;
then in the past: it must act). The backoff growth is still asserted, from the stored `last_attempt_at` / `next_attempt_at`
(computed at failure time, not wall-clock dependent). Passes 3 of 3. The other reliability tests only wait *at least* a short
time before asserting something happens, or assert something never happens over a long span, so a slow machine cannot break
them in this way.
**2. `test_concurrent_identical_amendment_upload_is_idempotent` (older, D-024/D-029; not changed).** Fails on some runs with
one or two of the three "concurrent" uploads answered `409 ILLEGAL_TRANSITION` ("current status: DRAFT"): the late request
arrives after the winner has already finished and moved the document to DRAFT, so the three requests were not overlapping.
The test needs genuine overlap, which scheduling does not guarantee. **Is it caused by REL-01? Not shown, and a matched
comparison says no.** Failure counts: baseline `4fec3f8` run from a temporary worktree 0 of 52; HEAD run from the repo
directory 6 of 37 (3/12, 2/20, 1/5); but HEAD run from a temporary worktree **0 of 20**, in a run interleaved with the
baseline's 0 of 20. With both trees run from the same kind of location, only the code differs, and the result is 0 and 0. What
correlated with failure was running from the main checkout on this machine, for a reason I did not isolate (candidates not
tested: scanning of the repo directory, different file-system caching, other processes in the session). **Superseded by D-048:** this paragraph originally concluded "leave it". The cause was then confirmed to be a real
gap, not only a scheduling artefact (the router's status gate rejects a late identical retry before the replay logic runs), and
the behaviour and the test were changed. See D-048.

### D-047 — `test_old_stuck_documents_are_not_auto_sent_until_an_admin_requeues` depended on the owner's `.env` (CI red on `7ae1218`)
**Problem.** CI failed this test on both the first run and the re-run: `await_count 0 == 1` on the last assertion, with the log
line `anchor worker: chain read failed (NOT_CONFIGURED) ... CONTRACT_ADDRESS is not configured`. Hypothesis: the test only passes
locally because `.env` supplies chain settings.
**Reproduced before any fix.** A clean `git worktree` of `7ae1218` with **no `.env`**, its own Mongo + RustFS started from that
worktree's `docker-compose.yml` (so the `minioadmin` defaults CI uses), and only CI's five env vars (`MONGODB_URI`,
`STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_BUCKET`): the test fails at the same assertion with
the same log lines (`chain read failed (NOT_CONFIGURED)`, `permanent failure (NOT_CONFIGURED)`).
**Cause (from the code, `anchor_confirmer._attempt`).** Step 2 calls `chain.get_onchain_anchor(...)` ("does the chain already
hold it?") *before* step 4's send. The test patches only `chain.anchor_hash` (the send), so the read is real. On the runner the
read raises `BlockchainNotConfigured`, the worker records a (correct) failure and never reaches the send. On the owner's machine
`.env` sets a real Sepolia RPC URL, wallet key and contract address, so the **read goes out to the public network** and returns
"not anchored"; the test passed by accident, and was network-dependent and slow-ish there. **The re-queue path is not
buggy**: the worker refused to send because it could not read the chain, which is the intended behaviour.
**Alternatives**
- **(a) Stub the chain read (`chain.get_onchain_anchor` -> `{"exists": False}`) next to the existing `anchor_hash` spy.** The
  test is about the age cutoff and the re-queue, so both chain calls the worker makes on this path are faked, and it needs no
  chain setting and no network on any machine.
- **(b) Monkeypatch `CONTRACT_ADDRESS` (and RPC URL / wallet key) to dummy values.** Gets past `NOT_CONFIGURED`, but the read
  then tries to connect to the dummy RPC and fails as `RPC_UNREACHABLE` (transient): still no send. It would also need a fake
  chain behind the URL to mean anything.
- **(c) Run it against the local Hardhat node (`local_chain` fixture).** Hermetic, but heavy (a node process, compiled
  artifacts) for a test that does not care what the chain holds, and it would no longer count sends through a spy.
**Decision: (a).** One new patch, scoped to the test. No application code changes. The owner's suggestion to use
`monkeypatch` for chain settings is satisfied in spirit (the test sets what it needs explicitly rather than inheriting `.env`);
(a) is preferred over (b) because settings alone cannot make the read succeed.
**Also checked.** Whole backend suite in the same clean no-`.env` worktree, to find any other test that leans on the owner's
config; results are recorded below.
**Outcome of D-047 (test-only change; no application code touched).**
- With the one-patch fix, the whole `test_anchor_attention.py` file passes in the clean no-`.env` worktree (21 passed).
- **The whole backend suite in that clean worktree** (no `.env`, CI's five env vars only, Mongo + RustFS from that worktree's
  compose, Hardhat artifacts linked in from the main checkout): **268 passed, exit 0, coverage 93.8%** (6 min 16 s). So no other
  test depends on the owner's local config; nothing else needed fixing. The worktree and its containers were removed afterwards.
- **Limit of this evidence:** the clean run was on Windows, not the runner's Ubuntu 24.04, so it shows the `.env` dependency is
  gone, not that CI will be green; the second CI failure (D-048, next) is unrelated to this one.

### D-048 — A late identical amendment upload replays with 201 instead of 409 `ILLEGAL_TRANSITION` (replaces D-046's "leave it")
**Problem.** `test_concurrent_identical_amendment_upload_is_idempotent` failed on the CI runner once (`[201, 201, 409]`) and
passes on re-run. D-024 and D-029 promise that an identical retry (same uploader, same bytes) is idempotent: it returns the
version already accepted, with 201 and no second audit row.
**Confirmed from the code (this is a behaviour gap, not just scheduling).** `documents/router.py` `upload_document` reads the
document once and, before calling the service, requires `AMENDMENT_REQUESTED` or "`DRAFT` with `review_feedback` set"
(router.py lines 152-161), otherwise it raises `IllegalTransition` (409). Once the first upload finishes the document is `DRAFT`
with no `review_feedback` (an amendment, not a review correction), so **any identical retry that arrives after the winner
finished is rejected at the gate and never reaches `create_next_version`**, whose replay logic (service.py: the `DuplicateKeyError`
branch, and the DRAFT-correction branch) therefore only works for requests that were already past the gate. The same happens for a
real client: the first response is lost or slow, the client retries, and gets a 409 for an upload that actually succeeded.
**Alternatives**
- **(a) Replay in the gate.** When the status gate fails, ask the service whether this request is an exact replay of the latest
  version, and answer it with 201 and that version; otherwise raise the same 409 as today. Narrow conditions, below.
- **(b) Keep the 409 and make the test accept `201` or `409`.** Zero risk, but it writes the flaw into the test, contradicts
  D-024/D-029, and leaves real clients with a misleading error after a successful upload. It also stops the test saying anything
  about idempotency (any mix of 201/409 would pass).
- **(c) Move the whole gate into the service under a re-read of the document.** Same outcome as (a) with a larger refactor of a
  concurrency-sensitive path (D-029 shows how easy this is to get wrong); no benefit over (a).
**Decision: (a).** A request is a replay only if **all** of these hold, otherwise the 409 is unchanged:
1. the caller already passed JWT, RBAC (`document:amend`) and geofence, and the bytes' SHA-256 must equal an already-accepted version's (so they already passed `validate_upload` once; bytes that
   would not pass can never match); the order of Guardrail #5 is unchanged, the replay check is the "action" step;
2. the document is `DRAFT` (not submitted, in review, approved, `ACTIVE`, rejected or archived, so a replay cannot move or
   resurrect a document in any other state);
3. its latest version has `version_no >= 2` and a `prev_version_hash` (an amendment version, never a first upload: a fresh,
   never-submitted v1 still does not qualify, per D-015), and is itself `DRAFT`;
4. that version's `uploaded_by` is the caller and its `sha256` equals the SHA-256 of the received bytes.
A replay writes nothing: no new version row, no storage object, no status change, no audit row (as in D-024), so Guardrail #7
is untouched (nothing in `document_versions` is written). A different uploader, different bytes, or any later state gives the
same 409 as before.
**Stated limit.** After the amended version is *submitted*, an identical retry gets 409 (state moved on); that is deliberate and
tested. A replay also does not re-check who currently owns the document: authorisation is the RBAC check plus "you uploaded
that exact version".
**How it is checked.** The test no longer depends on scheduling: it posts the winner, then posts the identical request *after* it
finished (the exact ordering that failed), and expects 201 with the same `version_id`, still only V1 and V2, one `UPLOAD` audit
row, one stored object. The three-way concurrent test is kept; with this change every interleaving yields `[201, 201, 201]`.
Negative tests (each must give 409 `ILLEGAL_TRANSITION` and leave `[V1, V2]` unchanged): different uploader with identical
bytes; same uploader with different bytes; identical retry after the version was submitted; identical v1 bytes on a fresh
never-submitted DRAFT; identical retry on an `ACTIVE` document.
**Outcome of D-048.**
- Code: `documents/service.py` `find_amendment_replay` (new, writes nothing) and the status gate in `documents/router.py`
  `upload_document`, which now asks it before raising `ILLEGAL_TRANSITION`.
- **Mutation check:** with the two app files reverted, `test_late_identical_amendment_upload_replays_with_201` fails
  (deterministically, it forces the late ordering); with the change it passes. The five negative tests pass either way (they guard
  the new path against loosening) and the fresh-v1 test pins D-015.
- Full backend suite with the owner's `.env`: **274 passed, exit 0, 93.82% coverage**. In a clean no-`.env` worktree of the
  commit (CI's five env vars only): **274 passed, exit 0, 93.78%**. `ruff check app tests`: exit 0. `pip_audit -r requirements.txt
  --no-deps`: exit 0, no known vulnerabilities.
- Not shown: that CI's Linux runner is green, and that the original `[201, 201, 409]` can no longer occur under real
  scheduling beyond the forced ordering plus the unchanged three-way concurrent test (which passed in both runs here).

## 2026-10-05 — REL-04: verification must not degrade silently

### D-049 — Verify tells "chain unreachable" from "not anchored", flags and audits what it cannot explain, and cannot hang
**How each outcome is decided today (read from `verify/service.py`, before any change).**
- Storage: `storage.get_object` raising *anything* -> `503 STORAGE_UNAVAILABLE`. "Object gone" and "storage down" look the same;
  no record, no audit row.
- Chain: `get_onchain_anchor(document_id, version_no)` raising *anything* -> replaced by `{"exists": False}` (lines 122-123).
- Verdict: no on-chain hash -> `NOT_ANCHORED`; else `VERIFIED` only if recomputed == stored == on-chain, otherwise `MISMATCH`.
  Only `MISMATCH` sets `integrity_flag = TAMPERED`. Audit: `VERIFY_FAIL` / `VERIFY_PASS` / `VERIFY_NOT_ANCHORED` (the catch-all).
- **The 2026-10-03 17:25 record** ("Contract - Umbrella Logistics (006)", read-only query of the dev DB, nothing written):
  history VERIFIED 17:24:33, **NOT_ANCHORED 17:25:40**, VERIFIED 2026-10-04 10:00; the version has `anchored: true` and a CONFIRMED
  anchor row; no flag; audit `VERIFY_NOT_ANCHORED` at 17:25:40. It came from the swallow at lines 122-123 (exception -> `exists:
  False` -> `onchain_hash None` -> `NOT_ANCHORED`). The stored row cannot by itself tell "the RPC raised" from "the contract
  said no", which is the defect; here the same `version_no` verified on both sides of it and the RPC was dead.
- **Why verify hangs (measured, web3 7.6.1, local sockets only):** a refused connection fails in 2.1 s, but a node that accepts
  and never answers takes **152 s** to raise (30 s default timeout x 5 retries of `eth_call`).
- **The lookup key is the mutable version row.** `(document_id, version_no)` is read from `document_versions`, and the anchor row
  stores no `version_no`. Edit `version_no` (R13: bytes + `sha256` + `version_no: 99`) and the chain answers "no such anchor".
- **A test encodes the bug:** `test_clear_refuses_when_the_chain_cannot_be_read` asserts the refusal says `NOT_ANCHORED`.

**Alternatives**
- **(A) Minimal:** add only `CHAIN_UNREACHABLE` and a bounded timeout. Fixes the 17:25 case, leaves the key-edit/reset hole: an
  anchored version whose anchor "vanished" is still a grey `NOT_ANCHORED`.
- **(B) A + `ANCHOR_MISSING` and `FILE_MISSING` with a flag and audit.** The chain *answered* "no" but the database itself says
  the version was anchored (`anchored`, a CONFIRMED anchor row, or a post-anchor status) -> red result, flag, audit. Chain
  *unreachable* -> amber, audited, never a verdict.
- **(C) B + derive the key from the anchor's tx input (chain-derived), and/or a reconciliation job scanning `AnchorCreated` events
  (REL-04 options (c)/(b)).** (c) needs a tx hash (adopted rows have none) and an extra RPC; (b) is a new worker duty (Guardrail
  #10 interpretation) and a larger change. **Deferred, not dropped** (see Limits).
- Flag vocabulary for the new red results: **(i) reuse `TAMPERED`** (no UI/clear changes, but a testnet reset or a lost object
  would be labelled "tampered", an overstatement in the spirit of Guardrail #6) or **(ii) a new flag value `UNCONFIRMED`**
  ("integrity could not be confirmed"), clearable by the same D-025 rule. **(ii) chosen.**
- "Contract returns nothing": treat the empty/undecodable `eth_call` as "no answer", or check `eth_getCode`? A redeployed/reset
  chain has no code at `CONTRACT_ADDRESS`, so the call returns `0x`; that is *definitive* (the anchor is gone), whereas an
  empty reply from a node that does have the code is not. **Check `eth_getCode`** (one extra read, only on that failure path).

**Decision: (B)**, with flag (ii) and the `eth_getCode` check. Outcome table (`claims` = the DB says this version was anchored:
`version.anchored`, or version status in {BLOCKCHAIN_ANCHORED, ACTIVE, SUPERSEDED}, or a CONFIRMED anchor row; `local_ok` =
recomputed == stored):

| chain says | claims | local_ok | result | flag | audit action |
|---|---|---|---|---|---|
| anchor exists, equal hashes | any | yes | `VERIFIED` | - | `VERIFY_PASS` |
| anchor exists, other hash | any | any | `MISMATCH` | `TAMPERED` | `VERIFY_FAIL` |
| exists = false (or contract not deployed) | no | any | `NOT_ANCHORED` | - | `VERIFY_NOT_ANCHORED` |
| exists = false (or contract not deployed) | yes | yes | **`ANCHOR_MISSING`** | `UNCONFIRMED` | **`VERIFY_ANCHOR_MISSING`** |
| exists = false (or contract not deployed) | yes | no | `MISMATCH` (file != recorded hash) | `TAMPERED` | `VERIFY_FAIL` |
| RPC error / timeout / not configured / bad reply | yes | no | `MISMATCH` (needs no chain) | `TAMPERED` | `VERIFY_FAIL` |
| RPC error / timeout / not configured / bad reply | otherwise | - | **`CHAIN_UNREACHABLE`** | none | **`VERIFY_CHAIN_UNREACHABLE`** |
| object authoritatively not found | any | n/a | **`FILE_MISSING`** | `UNCONFIRMED` | **`VERIFY_FILE_MISSING`** |
| any other storage failure | any | n/a | HTTP 503 `STORAGE_UNAVAILABLE` (as before) | none | **`VERIFY_STORAGE_UNAVAILABLE`** |

Details fixed by this decision:
- `UNCONFIRMED` is set only if the document has no flag (it never downgrades `TAMPERED`); `MISMATCH` still overrides.
- Responses and records gain an additive `reason` (a fixed code: `RPC_UNREACHABLE`, `CHAIN_TIMEOUT`, `NOT_CONFIGURED`,
  `CONTRACT_NOT_DEPLOYED`, `CHAIN_READ_FAILED`), never exception text, so an RPC URL with a key cannot leak (Guardrail #2, D-020).
  `recomputed` becomes nullable (`FILE_MISSING` has no bytes). `result` gains the three new values. HTTP status stays 200: the
  verification ran and produced a verdict ("could not verify" is a result, and is recorded).
- **Bounded read.** New setting `CHAIN_READ_TIMEOUT_SEC` (default 10). `get_onchain_anchor` uses its own read-only `Web3` (HTTP
  timeout = the setting, **no retries**) and an outer `asyncio.wait_for` deadline, and raises a timeout error. The shared signing
  `Web3` and the anchor/send path are untouched. The worker and `/blockchain/anchor` also use this read and become bounded.
  Not changed: the synchronous storage call (REL-05).
- **D-025 clearing:** accepts `TAMPERED` or `UNCONFIRMED`; still clears only if every anchored version re-verifies to exactly
  `VERIFIED`. `CHAIN_UNREACHABLE` is "unable to verify" in the refusal text and audit meta, never a pass.
- `reports` gains additive counts for the three new results so they are not silently absent from the summary.
- The one existing test that asserts `NOT_ANCHORED` for an unreachable chain is changed to the new, correct result; that is the
  intended behaviour change, not a loosened check.
- No transaction is sent anywhere in this change; the dev database is not written (tests use the throwaway test DB and a local
  Hardhat node).

**Limits (stated, not claimed away).** (1) An attacker who edits `version_no` *and* clears every "claims anchored" signal
(`anchored`, status, and deletes/changes the CONFIRMED anchor row) still gets a grey `NOT_ANCHORED`; closing that needs
(b)/(c) above and remains open under REL-04. (2) `UNCONFIRMED` after a chain reset is a true statement ("could not be
confirmed"), not a proof of tampering; recovery tooling is BC-02. (3) During an outage verification of an anchored, unmodified
file stays inconclusive; nothing in this change can make it conclusive without the chain.

**Test plan (written first, shown failing on the pre-change code, hard timeouts on every one).** Chain refused; chain accepts but
never answers (a local blackhole socket) bounded; contract has no code; anchored version with edited `version_no`; the R13 forged
bytes + forged hash + `version_no: 99`; never-anchored with edited `version_no` stays `NOT_ANCHORED`; stored file missing;
other storage failure; hash mismatch with the chain down; the 17:24/17:25/10:00 sequence (history shows VERIFIED,
CHAIN_UNREACHABLE, VERIFIED, no NOT_ANCHORED, no flag); clearing refused on an unreachable chain and allowed for `UNCONFIRMED`
once repaired; no secret in any response/record/audit row. Every chain setting is set explicitly (no `.env`).
