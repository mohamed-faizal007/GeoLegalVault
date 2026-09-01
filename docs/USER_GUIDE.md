# User Guide — GeoLegalVault

This guide covers what each role can actually do in the app. Every action below runs
through the same pipeline: sign in → the app checks your role → for location-sensitive
actions, your browser is asked for its current position and the server independently
checks it against your assigned zone(s). If a step is blocked, the app tells you which of
those three checks failed (login required, wrong role, or outside your authorized
location) — it never fails silently.

Sidebar items you don't have permission for simply don't appear; this isn't a bug if your
menu looks shorter than a colleague's with a different role.

## Signing in

Go to the **Login** page and enter the email/password an Administrator gave you (there is
no self-signup). If you get logged out mid-session, a fresh sign-in is required — the app
keeps you signed in quietly in the background for a while via an automatic token refresh,
but that refresh itself eventually expires too.

## All roles: Dashboard, Geofence Status, Settings

- **Dashboard** — your role badge, counts, and a quick view of documents you own in
  DRAFT.
- **Geofence Status** — shows whether you're currently inside a zone you're assigned to,
  with your reported coordinates and GPS accuracy. Check this *before* trying an
  upload/approve/amend if one of those unexpectedly gets blocked — a red/absent badge here
  is why.
- **Settings** — change your own password.

## Legal Officer

Can upload, submit, amend, approve, and verify. Cannot review (a different person must
review what you submitted — maker/checker).

1. **Upload** a document (you'll need to be inside an assigned geofence): pick a file,
   fill in title/type/classification/tags, submit. You'll see its SHA-256 fingerprint
   immediately on the resulting Document Details page — write it down if you want to
   compare it against Verify's output later.
2. Open the document and click **Submit** to send it for review.
3. Once a Reviewing Officer has approved it for you, open it and click **Approve** — this
   is the one action that also anchors the fingerprint on-chain, automatically, no extra
   click. You'll see the status move to BLOCKCHAIN_ANCHORED and then ACTIVE.
4. To correct an already-ACTIVE document, open it and click **Amend**, give a reason, and
   upload the corrected file. This creates a new version (V2) that goes through the same
   submit/review/approve cycle — the original V1 is never deleted or edited, only marked
   superseded once V2 goes live. Both remain independently checkable via Verify.
5. **Verify** any version at any time from its Document Details / Version History page.

## Reviewing Officer

Can review submissions; cannot upload, amend, or approve.

1. Open a document in status SUBMITTED and click **Review**.
2. Approve it forward (moves to PENDING_APPROVAL, awaiting a Legal Officer's final
   approval) or request changes with a required comment (sends it back to DRAFT for the
   uploader to fix). You cannot review something you uploaded yourself.

## Authorized Staff

Can upload, submit, amend, and verify — the same document-creation abilities as a Legal
Officer, minus approval (someone else, a Legal Officer, must approve what you submit).

## Auditor

Read-only everywhere, plus the one page nobody else sees:

- **Audit Logs** — every security-relevant action in the system: who did what, to what,
  when, from where, and whether it succeeded — including geofence denials and failed
  verifications. Filter by actor, action, result, or date range.
- Can also browse the Document Repository and run Verify, but cannot upload, submit,
  review, approve, amend, or archive anything.

## Administrator

Manages the system, not the document workflow — deliberately cannot upload, review, or
approve (a super-admin silently approving its own uploads is exactly the scenario
maker/checker exists to prevent).

- **Admin Panel** — tabs for Users, Geofences, Reports, and System Health.
  - **Users:** create accounts, assign a role and one or more geofences, deactivate an
    account (accounts are never hard-deleted, even after deactivation).
  - **Geofences:** define named zones as a polygon on a map (or paste GeoJSON). A zone can
    be deactivated but not deleted once it's ever been assigned to anyone.
  - **Reports:** aggregate counts — documents by status/type, how many anchor attempts
    succeeded vs. failed, recent verification pass/fail counts, geofence-denial counts.
  - **System Health:** the same reachability check (`/health`) shown as a page.
- Can also archive an ACTIVE/SUPERSEDED document (hides it from the default repository
  view; every version and anchor stays intact and still verifiable via an explicit
  "show archived" filter).

## Understanding a Verify result

| Badge | Meaning |
|---|---|
| 🟢 **VERIFIED** | The file's current bytes hash to exactly the value recorded at upload *and* the value anchored on-chain. Nothing has changed since it was approved. |
| 🔴 **MISMATCH — tamper detected** | The file's current bytes do **not** match. Something changed the stored file (or someone tried to also change the database record to cover it up — Verify still catches this because it also checks against the immutable on-chain hash, not just the database). The document is automatically flagged. |
| ⚪ **NOT ANCHORED YET** | This version hasn't been approved/anchored yet — not an error, just not eligible for the full 3-way check yet. Its recomputed hash is still compared against the stored one. |

A **red MISMATCH does not mean the platform failed** — it means the platform *caught*
something it's specifically designed to catch. That's the point of the whole system.
