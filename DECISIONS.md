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
