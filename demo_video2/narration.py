"""Single source for the narration. One sentence = one on-screen step (a "beat"), so audio and picture are synced
per sentence (see scenes/common.py::Scene.beat and assemble.py).

    python narration.py            -> writes audio/<sid>_<key>.txt (what the voice reads)
    assemble.py                    -> writes NARRATION_SCRIPT.md with final-video timestamps

Each scene: id, title, page, action, lines [(key, text)], backend, evidence, troubleshooting.
Plain spoken English; terms are defined right after first use. Wording rules: Ethereum Sepolia TESTNET, tamper-evident
(detects, does not prevent), policy-level geofencing, prototype; the app has no REJECTED state ("changes requested").
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

SCENES = [
    dict(
        id="s01", title="Scene 1 - The problem and the idea",
        page="Title card, then two slides (no application screen)",
        action="The problem; what GeoLegalVault does; what the next twenty minutes show.",
        lines=[
            ("a1", "Legal documents face two quiet risks."),
            ("a2", "First, a file can be changed after everyone agreed to it, and nobody notices."),
            ("a3", "Second, anyone with a login can upload or approve from anywhere."),
            ("b1", "GeoLegalVault is a prototype that tackles both."),
            ("b2", "Uploads and approvals are allowed only from an approved area. That area is called a geofence, a virtual boundary drawn on a map."),
            ("b3", "Every document is reviewed and approved by different people, so nobody approves their own work."),
            ("b4", "When a version is approved, a fingerprint of the file, called a SHA-256 hash, is written to the Ethereum Sepolia test network."),
            ("b5", "Later, anyone can recompute the fingerprint and see whether the file still matches. This is tamper-evident: changes are detected, not prevented."),
            ("b6", "In about twenty minutes we follow one fresh document through its whole life: upload, approval, anchoring, tampering, an amendment, a download, and archive."),
            ("b7", "Everything you will see is the real running system, on a test network. Where the screen cannot show something, like database records, I label it a supplementary view."),
        ],
        slides={"a": ["a1", "a2", "a3"], "b": ["b1", "b2", "b3", "b4", "b5", "b6", "b7"]},
        backend="None.", evidence="Slides only.", troubleshooting="None.",
    ),
    dict(
        id="s02", title="Scene 2 - Login, roles, clearance and names",
        page="/login, then the Dashboard, for three users in three separate browser sessions",
        action="Authorized Staff, Legal Officer and Administrator each sign in; the welcome line shows a name; the counts differ by clearance.",
        lines=[
            ("k1", "First, login and roles. There are five roles: Administrator, Legal Officer, Reviewing Officer, Authorized Staff and Auditor. A role is a set of permissions."),
            ("k2", "Here Authorized Staff is signed in. The welcome line shows the person's name, not a database id. The menu has Upload, but no Admin Panel and no Audit Logs."),
            ("k3", "These counts come from the server, and they differ for each person. In total the vault holds twenty-one demo documents, two of them archived, and archived ones are left out of these counts."),
            ("k4", "Next, a Legal Officer signs in, in a completely separate browser session. This role has a higher clearance, so it sees more documents."),
            ("k5", "Then an Administrator. Their menu shows the Admin Panel and Audit Logs, but no Upload. Administrators manage users and zones, but they cannot upload, review or approve."),
            ("k6", "Every person also has a clearance level: Public, Internal, Confidential, Restricted or Top Secret. The menu is only a convenience. The server checks role and clearance on every single request."),
        ],
        backend="POST /api/v1/auth/login (auth/service.py); role, name and clearance come from the users collection on every request (core/rbac.py, core/clearance.py).",
        evidence="Different sidebars per role; the name in the welcome line; different document counts per person.",
        troubleshooting="Login fails: check that the demo backend is on port 8001 and the demo users were seeded (scripts/seed.py --demo). Never enter a wrong password more than twice on a real account.",
    ),
    dict(
        id="s03", title="Scene 3 - Administrator: zones and users",
        page="/admin (Geofences tab, Users tab)",
        action="Admin views the zone, then creates a throwaway low-clearance user.",
        lines=[
            ("k1", "Now the Administrator's Admin Panel. The Geofences tab lists the approved zones."),
            ("k2", "A zone is a polygon: a list of longitude and latitude pairs, always in that order. The form previews the approximate centre of the ring you type, and asks the administrator to confirm the place. That preview is only a visual aid. Our demo zone, HQ Campus, is the small box listed below, around latitude eleven point six seven and longitude seventy-eight point one five. Every request is tested against it on the server."),
            ("k3", "Now the Users tab. People are shown by name, with their role and clearance."),
            ("k4", "We create a throwaway account with the Auditor role. A new user starts at the lowest clearance, Public, and the password field is masked."),
            ("k5", "The new account appears in the table. We will use it later, to show a hidden document and the login protection."),
        ],
        backend="GET/POST /api/v1/geofences, /api/v1/users (geofences/service.py, users/service.py).",
        evidence="Zone list; new user in the table with clearance Public.",
        troubleshooting="Create-user 409: the email already exists (the throwaway email carries the date).",
    ),
    dict(
        id="s04", title="Scene 4 - Upload version one inside the zone",
        page="/documents/upload, /documents/<id>, /documents/<id>/versions, plus two supplementary views",
        action="Authorized Staff uploads DEMO-20261022-Lease (Internal) from inside the zone, sees Draft, then submits it.",
        lines=[
            ("k1", "Now the main flow, with one fresh document. Authorized Staff opens Upload. The page shows the location the browser reports. On a real device that comes from GPS or Wi-Fi. In this recording a test harness supplies it, and the label says so. The server still validates it."),
            ("k2", "We enter a title, the type Lease, the classification Internal, and pick a sample PDF."),
            ("k3", "On Upload, the server checks, in a fixed order: your token, your role, your location, then the file. Then it stores the file, computes the hash and writes an audit entry. The document is saved as a Draft, owned by Authorized Staff."),
            ("k4", "In this supplementary view, the real database shows the document row and the version row. The highlighted field is the SHA-256 fingerprint of the file. It turns any file into sixty-four characters, and changing one byte changes all of them."),
            ("k5", "The file itself is not in the database. It sits in private object storage, called RustFS here and Cloudflare R2 in production, under a server-made key that includes the hash. This demo shares one bucket with the development setup, but this document has its own object."),
            ("k6", "The uploader then submits the document for review, and the status becomes Submitted."),
            ("k7", "In the app, Version History shows the fingerprint, shortened. The full value is in the database."),
        ],
        backend="POST /api/v1/documents (documents/router.py) -> services/hashing.py -> services/storage.py put_object -> insert documents + document_versions -> audit UPLOAD; POST /documents/{id}/submit.",
        evidence="Status Draft then Submitted; version row with sha256 and storage_key; object listed in the bucket.",
        troubleshooting="GEOFENCE_DENIED: the user must have the zone assigned and the browser location must be inside it. 413: file over the size limit. MIME_MISMATCH: the content does not match the type.",
    ),
    dict(
        id="s05", title="Scene 5 - Upload refused: outside the zone, and poor accuracy",
        page="/documents/upload with two different browser locations, then one supplementary view",
        action="Same user and form: first about 100 km outside the zone, then inside but with 500 m accuracy.",
        lines=[
            ("k1", "Now the negative cases. The same user tries again, but the browser reports a place about one hundred kilometres outside the zone."),
            ("k2", "The server answers GEOFENCE_DENIED, and nothing is stored. The server decides inside or outside, never the browser."),
            ("k3", "Now the location is inside the zone, but very imprecise: plus or minus five hundred metres."),
            ("k4", "The server refuses that too, with LOCATION_LOW_CONFIDENCE. This is called fail-closed: if the system is not sure, it says no. This server allows up to three hundred metres of uncertainty."),
            ("k5", "The zone denial is written to the audit log with the claimed position, as you can see here. The low-confidence refusal is different: it happens before the zone check, and it goes to the application log, not to the audit log."),
            ("k6", "An honest limit: browser location can be faked, for example with developer tools. So geofencing here is a policy control that adds a layer. It is not a guarantee of where someone is. The tamper-evidence comes from the blockchain, not from the geofence."),
        ],
        backend="services/geofence.py check_location: accuracy limit, then freshness, then a MongoDB point-in-polygon query against the user's assigned zones. LOCATION_LOW_CONFIDENCE 422, LOCATION_STALE 422, INVALID_LOCATION 422, GEOFENCE_DENIED 403.",
        evidence="Red banners with the error codes; audit_logs row GEOFENCE_DENIED.",
        troubleshooting="LOCATION_LOW_CONFIDENCE for a good reading: check GEO_ACCURACY_MAX_M (this machine uses 300) and that the right backend is on port 8001.",
    ),
    dict(
        id="s06", title="Scene 6 - Review, maker-checker and approval",
        page="Document Details for three roles; one supplementary API view",
        action="A seeded self-approval attempt is refused; the Reviewing Officer reviews the lease; a different Legal Officer approves it inside the zone (transaction 1).",
        lines=[
            ("k1", "Next, review and approval. This uses maker-checker, meaning the person who made a document must not be the one who checks it."),
            ("k2", "Here a Legal Officer opens a seeded document that they uploaded themselves. There is no Approve button, and the page says someone else must approve it."),
            ("k3", "If they call the server directly anyway, from inside the zone, the answer is MAKER_CHECKER_VIOLATION. That is a real response, shown in a supplementary view. Nothing was changed."),
            ("k4", "Now the real path for our lease. A Reviewing Officer, a different person from the uploader, opens it and chooses Review."),
            ("k5", "They pass the review, and the status becomes Pending Approval. A reviewer can instead request changes, which sends it back to the uploader. This app has no rejected state."),
            ("k6", "Then a Legal Officer who did not upload it opens the document. The Approve button is there. The server checks the location first."),
            ("k7", "Approval starts anchoring automatically, and there is no anchor button. The backend's own wallet signs the transaction, never the user. This is a real transaction on the Sepolia test network, the free test version of Ethereum. I have trimmed the wait for the block."),
            ("k8", "The status becomes Active. The approval cost a tiny amount of test Ether, which has no real value."),
        ],
        backend="POST /documents/{id}/review (workflow.review); POST /documents/{id}/approve (geofenced; workflow.approve -> blockchain/service.py -> services/blockchain.py -> DocumentAnchor.anchor). Checks: RBAC approve:perform, geofence, enforce_maker_checker (before anything touches the chain).",
        evidence="Statuses Submitted -> Pending Approval -> Approved -> Active; HTTP 403 MAKER_CHECKER_VIOLATION.",
        troubleshooting="Document stays APPROVED: the transaction was not confirmed inside the request window and the optional anchor worker is not running. This recording raised ANCHOR_CONFIRM_POLL_ATTEMPTS for the backend process only.",
    ),
    dict(
        id="s07", title="Scene 7 - What is anchored on Sepolia",
        page="/documents/<id>/versions, /versions/<id>/blockchain, Etherscan, one supplementary view",
        action="Open the anchor record: recorded hash and live on-chain hash side by side; then the public Etherscan page.",
        lines=[
            ("k1", "Now, what exactly went on the blockchain. In Version History, version one is Active and marked Confirmed. We open View on-chain."),
            ("k2", "The Blockchain Anchor Record puts two hashes side by side. On the left, the hash recorded in our database. On the right, the hash the app has just read live from the contract on the Sepolia testnet. They are identical, and the page says Match."),
            ("k3", "The page also shows the network label, Sepolia testnet, the contract address, and the transaction hash, with a Copy button."),
            ("k4", "The smart contract, DocumentAnchor, stores only four things per document version: the hash, the version number, an event type, and the block time. The PDF, its filename and any person's name are not on-chain, because a blockchain is public and permanent. The contract also refuses a second anchor for the same version."),
            ("k5", "On the public Etherscan page for the Sepolia testnet, the transaction shows Status: Success, and a tiny fee."),
            ("k6", "One service wallet in the backend signs every anchor. That is a trust assumption we come back to at the end. And there is no Merkle tree: each file gets one hash."),
        ],
        backend="GET /api/v1/blockchain/anchor/{version_id}; contract call getAnchor(documentId, version); contracts/contracts/DocumentAnchor.sol.",
        evidence="Anchor record: Match banner, two equal hashes, Sepolia testnet label, Copy button; Etherscan: Status Success.",
        troubleshooting="Etherscan page blank: network or the site's bot checks; the transaction hash is on the Anchor Record page.",
    ),
    dict(
        id="s08", title="Scene 8 - Clearance: a hidden document is a 404",
        page="/documents and /documents/<id> as the Public-clearance user, then as the Administrator; two supplementary views",
        action="The throwaway user cannot see the Internal lease; the Administrator cannot open a seeded Confidential document.",
        lines=[
            ("k1", "Now clearance. The throwaway user has the lowest level, Public, and our lease is Internal."),
            ("k2", "In the repository the lease is simply not listed, because the server filters in the database query."),
            ("k3", "Opening its exact link shows the app's own wording: That item couldn't be found, or you don't have access to it."),
            ("k4", "In the supplementary view, the real document and a made-up id give exactly the same answer, 404 not found. We use 404 instead of 403, which means forbidden, because a 403 would confirm that the document exists."),
            ("k5", "The same rule applies to everyone. Here the Administrator, whose clearance is Internal, opens a seeded document classified Confidential, and also gets a real 404. Administrators manage the system, but get no automatic access to document content."),
            ("k6", "A refused attempt on a document that exists is still written to the audit log as ACCESS_DENIED, as highlighted. This is access control inside the application. It is not encryption."),
        ],
        backend="documents/access.py load_visible_document and core/clearance.py can_see; audit action ACCESS_DENIED.",
        evidence="Empty search result; 'couldn't be found' banner; two identical 404 bodies; ACCESS_DENIED audit rows.",
        troubleshooting="If the page spins for several seconds before the message, the UI is retrying the 404 request.",
    ),
    dict(
        id="s09", title="Scene 9 - Verify the genuine file: VERIFIED",
        page="/verify/<versionId>",
        action="Legal Officer clicks Run verification.",
        lines=[
            ("k1", "Now the core feature: verification. The Legal Officer opens Integrity Verification for version one."),
            ("k2", "When we run it, the server reads the stored file and recomputes its SHA-256. It compares that with the hash saved in the database at upload, and with the anchored hash it reads live from the Sepolia contract."),
            ("k3", "All three are identical, so the result is VERIFIED."),
            ("k4", "A database change alone, or a storage change alone, cannot produce a false VERIFIED, because the chain holds the original value."),
        ],
        backend="POST /api/v1/verify/{version_id} (verify/service.py): storage get_object, sha256, MongoDB document_versions.sha256, contract getAnchor; inserts a verification_records row and an audit row.",
        evidence="Green VERIFIED banner; three equal hashes.",
        troubleshooting="CHAIN_UNREACHABLE: the Sepolia RPC could not be read; no verdict is given.",
    ),
    dict(
        id="s10", title="Scene 10 - Tamper with the stored file, restore it, clear the flag",
        page="Supplementary views, /verify/<versionId>, Document Details as Legal Officer and as Administrator",
        action="Save the original bytes; demo/tamper.py changes one byte of this document's own object; verify (MISMATCH); restore and confirm the hash; verify (VERIFIED); the Administrator clears the flag.",
        lines=[
            ("k1", "Now the attack. First, for the demo, I save a copy of the original file bytes locally, and check that their hash equals the recorded fingerprint. That lets me put things back afterwards."),
            ("k2", "Now someone with direct access to the storage server changes one byte of the file, not through the app. This script bypasses the application on purpose, and it touches only this document's own object. The database and the blockchain still hold the original hash."),
            ("k3", "We run verification again. The result is MISMATCH, tamper detected. The recomputed hash is completely different, while the stored and on-chain hashes still agree. One changed byte gives a totally different hash. That is called the avalanche effect."),
            ("k4", "The document is also flagged as Tampered. The system made the change evident. It did not prevent it."),
            ("k5", "Now I write the original bytes back to the same storage key, and confirm that their hash matches the recorded SHA-256."),
            ("k6", "Verification returns to VERIFIED."),
            ("k7", "But the Tampered flag is still on the document. A later pass does not clear it automatically."),
            ("k8", "Only an Administrator can clear it. They choose Clear integrity flag, and must give a reason of at least ten characters, which is written to the audit log."),
            ("k9", "The app re-runs verification on every anchored version first, and only then clears the flag. The flag is gone, and the document is clean again."),
        ],
        backend="demo/tamper.py (put_object with byte 0 changed, latest version only); POST /verify/{id} -> MISMATCH -> documents.integrity_flag = TAMPERED and audit VERIFY_FAIL; POST /documents/{id}/integrity/clear (Administrator, reason >= 10 chars) -> INTEGRITY_CLEARED.",
        evidence="Red MISMATCH banner; Tampered badge; verification history MISMATCH then VERIFIED; flag cleared by the Administrator.",
        troubleshooting="Run tamper.py only with MONGODB_DB=geolegalvault_demo and the exact title. To restore, write the saved original bytes back to the same storage key (work/ folder).",
    ),
    dict(
        id="s11", title="Scene 11 - Amendment: version two",
        page="Document Details, /documents/<id>/amend, /documents/<id>/versions, /versions/<id>/blockchain, /verify/<id>",
        action="Request amendment (Legal Officer); upload V2 (Authorized Staff); submit; review; approve (transaction 2); Version History; proof of the hash link; verify V2 and V1.",
        lines=[
            ("k1", "Now an amendment, which creates version two. Documents are never edited in place. Each version is a new, immutable record."),
            ("k2", "A Legal Officer opens the active lease and chooses Request amendment. This is geofenced, so the location is checked."),
            ("k3", "They must give a reason. The document moves to Amendment Requested."),
            ("k4", "Now Authorized Staff uploads the amended file, version two. The title, type and classification are copied from the document and cannot change."),
            ("k5", "Version two starts as a Draft, and its uploader submits it."),
            ("k6", "The three-person rule applies again. The Reviewing Officer reviews version two."),
            ("k7", "And the Legal Officer, who did not upload it, approves. This sends a second real transaction on the Sepolia test network, for version two. Again I trim the wait."),
            ("k8", "In Version History, version two is Active and Confirmed. Version one now carries the grey Superseded badge. That is the only place the app says so. There is no separate current label: the Active badge marks the current version."),
            ("k9", "The hashes are shortened on that page, so this supplementary view shows the proof. The previous-hash field of version two equals, character for character, the SHA-256 of version one. There is no parent version id field. This hash link is the connection."),
            ("k10", "Version two has its own anchor, again with the recorded and on-chain hashes side by side, and a Match."),
            ("k11", "Verification of version two returns VERIFIED."),
            ("k12", "And version one still verifies, because its file, its hash and its anchor are untouched. The Verification page does not mention superseded at all."),
        ],
        backend="POST /documents/{id}/amend (geofenced) -> AMENDMENT_REQUESTED; POST /documents with amend_of (geofenced) -> create_next_version (version_no 2, prev_version_hash = V1 sha256); submit/review/approve act on the highest version_no; complete_promotion marks V1 SUPERSEDED when V2 is ACTIVE.",
        evidence="Version History: V2 ACTIVE + CONFIRMED, V1 grey SUPERSEDED; prev_version_hash equals V1 sha256; two anchors; both versions VERIFIED.",
        troubleshooting="V2 stays APPROVED: the anchor did not confirm in the request window; stop, do not start the worker for the recording.",
    ),
    dict(
        id="s12", title="Scene 12 - Download the current version",
        page="Document Details (Download), two supplementary views, a refused download",
        action="Download (geofenced, current version only); hash of the downloaded bytes equals the recorded SHA-256; ACCESS audit row; outside the zone and below clearance are refused.",
        lines=[
            ("k1", "Now download. The Download button gives the current version only, which is now version two. It is geofenced, so the location is checked first."),
            ("k2", "The server answers with a short-lived pre-signed link, valid for sixty seconds. The file never passes through the API. I will not show the link itself on screen."),
            ("k3", "To prove the download is genuine, the test harness fetched the file through that link and hashed it. The result equals the recorded SHA-256 of version two."),
            ("k4", "The download is audited as ACCESS, with the version id, as highlighted."),
            ("k5", "Now the real denials. From outside the zone, the same Download button is refused with GEOFENCE_DENIED."),
            ("k6", "And a below-clearance viewer who is inside an assigned zone gets a 404 for the same document, so the file is never even offered. The order of checks is the zone first, then clearance."),
        ],
        backend="GET /api/v1/documents/{id}/download (geofenced; documents/router.py -> storage.generate_presigned_get, TTL 60 s; audit ACCESS with meta.version_id).",
        evidence="Hash of downloaded bytes = documents version sha256; ACCESS audit row; GEOFENCE_DENIED banner; 404 for the Public viewer.",
        troubleshooting="The UI opens the pre-signed URL in a new tab; the recording captures it without displaying it. Download shows the current version only (V1 before V2 is Active).",
    ),
    dict(
        id="s13", title="Scene 13 - Archive",
        page="Document Details (Archive), Dashboard, Document Repository (default and Archived filter)",
        action="Legal Officer archives the fresh document from Active.",
        lines=[
            ("k1", "Finally, the end of the lifecycle: archive. The lease is Active, and it is in the repository list."),
            ("k2", "The Legal Officer opens it and chooses Archive. There is no reason field, and it is not geofenced."),
            ("k3", "The status is now Archived."),
            ("k4", "It has disappeared from the default Dashboard and Repository."),
            ("k5", "It appears when we filter the Repository on Archived."),
            ("k6", "Archiving keeps every version, anchor and file untouched. The Reports panel will count one more archived document. And the backend has no way to undo an archive: there is no restore route. Only direct database editing could change it."),
        ],
        backend="POST /api/v1/documents/{id}/archive (no body, not geofenced; ACTIVE only; Administrator or Legal Officer); audit ARCHIVE.",
        evidence="Status Archived; absent from default Repository; present under the Archived filter.",
        troubleshooting="409 ILLEGAL_TRANSITION: only an Active document can be archived.",
    ),
    dict(
        id="s14", title="Scene 14 - The other verification outcomes",
        page="/verify/<versionId> for a seeded draft, then one slide",
        action="Verify a seeded draft that was never approved: NOT_ANCHORED. One slide lists all six outcomes.",
        lines=[
            ("k1", "There are six possible verification results. One more, live: a seeded draft that was never approved."),
            ("k2", "The result is NOT ANCHORED. The file is intact, but there is no blockchain record to compare with. That is not an error and not an alarm."),
            ("s1", "Here are all six outcomes."),
            ("s2", "VERIFIED: the stored file, the recorded hash and the on-chain hash all agree. MISMATCH: the file differs from the record, which we saw."),
            ("s3", "NOT_ANCHORED: it was never approved, so there is nothing on-chain to compare, which we just saw."),
            ("s4", "ANCHOR_MISSING: the database says it was anchored, but the chain says no. FILE_MISSING: the stored file is gone. And CHAIN_UNREACHABLE: the blockchain could not be read, so there is no verdict at all."),
            ("s5", "I did not trigger those last three live. They are marked on the slide as not triggered live."),
        ],
        slides={"outcomes": ["s1", "s2", "s3", "s4", "s5"]},
        backend="verify/service.py verdict table.", evidence="Grey NOT ANCHORED banner; on-chain value 'not available'.",
        troubleshooting="None.",
    ),
    dict(
        id="s15", title="Scene 15 - Login protection",
        page="/login (throwaway account only), one supplementary view",
        action="Five wrong passwords on the throwaway account: Attempt 1 of 5 ... 5 of 5, then the lockout message.",
        lines=[
            ("k1", "Login also has protection. On the throwaway account only, I type wrong passwords on purpose."),
            ("k2", "The page counts the attempts. Attempt one of five."),
            ("k3", "Attempt two."),
            ("k4", "Attempt three."),
            ("k5", "Attempt four."),
            ("k6", "Attempt five. Sign-in is now paused for about a minute."),
            ("k7", "The next try is refused outright: too many attempts. That slows down password guessing."),
            ("k8", "In MongoDB, the login_rate_limits collection holds the counter for each email, and when the pause ends."),
        ],
        backend="POST /auth/login failure path; lockout counter in the login_rate_limits collection (auth/service.py).",
        evidence="Attempt 1 of 5 ... Attempt 5 of 5; 'Too many attempts' message; login_rate_limits row.",
        troubleshooting="The lockout lasts about one minute; wait before logging in as that account.",
    ),
    dict(
        id="s16", title="Scene 16 - Audit log, MongoDB and storage",
        page="/audit as Auditor (filters), Document Details, three supplementary views",
        action="Audit Logs at the top; action dropdown, actor search, document filter, View audit trail; then the real collections, id links and bucket.",
        lines=[
            ("k1", "Finally, where everything lives. The Auditor opens Audit Logs, and it opens at the top, newest first. Every action is a row: who, what, to what, and the result. Rows are only ever added."),
            ("k2", "The Action dropdown lists every action the log really contains. Here I pick Approve."),
            ("k3", "Actor search finds people by name or email. Here, Legal."),
            ("k4", "The document filter finds a document by its title, only among documents this person may open. Here, a seeded board resolution, and its trail."),
            ("k5", "For our lease, the same view is one click from the document page: View audit trail."),
            ("k6", "This is the whole life of the lease, with names instead of ids. The ids are secondary text underneath."),
            ("k7", "Next, the MongoDB collections. Users, geofences, documents and document versions are the authoritative data. The anchors collection is derived, because the chain is the real evidence. Verification records and audit logs are history."),
            ("k8", "The ids link them: a version points to its document, an anchor points to its version, and the storage key points to the file."),
            ("k9", "And the split: MongoDB holds state, fingerprints and audit. The private bucket holds the file bytes. The Sepolia contract holds the hash, version, event type and time."),
            ("k10", "One honest gap: the audit log has no hash chain yet, so someone with database write access could alter it. That is a planned improvement."),
        ],
        backend="GET /api/v1/audit and /audit/actions (audit/service.py); supplementary views are read-only pymongo and S3 list calls with secrets removed.",
        evidence="Audit table with names; filtered trail for the lease; JSON documents; bucket listing.",
        troubleshooting="Audit page empty: the account needs the audit:view permission (Auditor or Administrator).",
    ),
    dict(
        id="s17", title="Scene 17 - Reports",
        page="/admin, Reports tab, as Auditor",
        action="The Reports panel; the count note; end on Mismatches and the archived count.",
        lines=[
            ("k1", "The Reports panel gives the whole picture. The Auditor can open it too."),
            ("k2", "Anchors confirmed counts the successful transactions, including our two."),
            ("k3", "This note reconciles the counts. The Auditor can access twenty-two documents in total, including three archived. The Dashboard and Repository show nineteen, because they leave archived documents out."),
            ("k4", "Mismatches counts our tamper test, and the archived count went up by one, because we archived the lease."),
        ],
        backend="GET /api/v1/reports/summary (reports/service.py), clearance-filtered.",
        evidence="Mismatches card >= 1; 'including 3 archived' note; ARCHIVED bar.",
        troubleshooting="Counts depend on the viewer's clearance: an Administrator at Internal sees fewer.",
    ),
    dict(
        id="s18", title="Scene 18 - Summary and future work",
        page="Four slides",
        action="Components; honest limits; future work; the planned next version.",
        lines=[
            ("a1", "To summarise the parts. The front end is React. The back end is FastAPI in Python. MongoDB stores the data. RustFS in development, and Cloudflare R2 in production, store the files. web3.py talks to a Solidity smart contract on the Sepolia test network. Docker runs the services, and a CI pipeline runs the tests."),
            ("b1", "Honest limits. This is a prototype on a test network. Geofencing is a policy control, not proof of where someone is. A single service wallet signs every anchor. The audit log has no hash chain yet. There is one SHA-256 per file, with no Merkle tree. And verification detects tampering; it does not prevent it."),
            ("c1", "Future work includes the open items in the project's own tracker: stronger login and secret handling, called SEC-01 and SEC-03; deployment hardening, OPS-01; a hash chain for the audit log, CMP-01; and malware scanning of uploads. Also per-matter access, so that clearance can say this matter only, and richer display names."),
            ("d1", "There is also a planned next version that reduces how much you must trust the single service wallet. I won't describe its design here. Thank you."),
        ],
        slides={"a": ["a1"], "b": ["b1"], "c": ["c1"], "d": ["d1"]},
        backend="None.", evidence="Slides only.", troubleshooting="None.",
    ),
]

SLIDES = {
    "title": ("GeoLegalVault", ["Location-gated, approved and blockchain-anchored legal documents", "Prototype demo - Ethereum Sepolia TESTNET"]),
    "s01_a": ("The problem", ["A file can be changed after it was agreed, silently", "Anyone with a login can upload or approve from anywhere"]),
    "s01_b": ("The idea", ["Upload and approve only from an approved area (policy-level geofence)",
                           "Maker-checker: the uploader cannot approve",
                           "Approved version: its SHA-256 fingerprint goes on the Sepolia testnet",
                           "Verify later: tamper-evident. It detects changes; it does not prevent them"]),
    "s14_outcomes": ("Six verification outcomes", [
        "VERIFIED: stored file = recorded hash = on-chain hash",
        "MISMATCH: file differs from the record / chain (shown live)",
        "NOT_ANCHORED: never approved, nothing on-chain to compare (shown live)",
        "ANCHOR_MISSING: DB says anchored, chain says no (not triggered live)",
        "FILE_MISSING: stored object is gone (not triggered live)",
        "CHAIN_UNREACHABLE: chain could not be read - no verdict (not triggered live)"]),
    "s18_a": ("Components", ["React front end  |  FastAPI back end (Python)", "MongoDB: state, fingerprints, audit",
                             "RustFS (dev) / Cloudflare R2 (prod): private file storage",
                             "web3.py + Solidity contract on Ethereum Sepolia testnet", "Docker, CI tests"]),
    "s18_b": ("Honest limits", ["Prototype on a test network", "Geofencing is a policy control, not proof of location",
                                "One service wallet signs every anchor", "Audit log has no hash chain yet (CMP-01)",
                                "One SHA-256 per file, no Merkle tree", "Tamper-evident: detects changes, does not prevent them"]),
    "s18_c": ("Future work", ["SEC-01 / SEC-03: login and secret handling", "OPS-01: deployment hardening",
                              "CMP-01: hash chain for the audit log", "Malware scanning of uploads",
                              "Per-matter access (beyond one clearance level)", "Richer display names"]),
    "s18_d": ("Planned next version", ["Reduces how much you must trust the single service wallet", "Design not described in this demo"]),
    "end": ("Thank you", ["GeoLegalVault - prototype", "All screens recorded from the real running system"]),
}

# Words the voice should say differently (applied to the spoken text only; captions keep the written form).
PRON = [("SHA-256", "S H A two fifty six"), ("RustFS", "Rust F S"), ("R2", "R two"), ("FastAPI", "Fast A P I"),
        ("web3.py", "web three dot P Y"), ("MongoDB", "Mongo D B"), ("SEC-01", "S E C zero one"), ("SEC-03", "S E C zero three"),
        ("OPS-01", "O P S zero one"), ("CMP-01", "C M P zero one"), ("CI ", "C I "), ("PDF", "P D F"), ("GPS", "G P S"),
        ("Wi-Fi", "Wifi"), ("React", "React"), ("NOT ANCHORED", "not anchored"), ("login_rate_limits", "login rate limits")]


def spoken_text(text: str) -> str:
    for a, b in PRON:
        text = text.replace(a, b)
    return re.sub(r"(?<=[A-Z])_(?=[A-Z])", " ", text).replace("_", " ")


def all_lines():
    for sc in SCENES:
        for key, text in sc["lines"]:
            yield sc["id"], key, text


def write_audio_texts() -> int:
    d = HERE / "audio"
    d.mkdir(exist_ok=True)
    n = 0
    for sid, key, text in all_lines():
        f = d / f"{sid}_{key}.txt"
        t = spoken_text(text)
        if not f.exists() or f.read_text(encoding="utf-8") != t:
            f.write_text(t, encoding="utf-8")
            wav = f.with_suffix(".wav")
            if wav.exists():
                wav.unlink()  # stale audio for changed text
            n += 1
    return n


def write_markdown(timestamps: dict | None = None, beat_times: dict | None = None) -> None:
    """NARRATION_SCRIPT.md: per scene the page, action, every spoken sentence (with its timestamp in the final
    video when assemble.py supplies it), backend operation, expected evidence and troubleshooting."""
    out = ["# Narration script - GeoLegalVault demo v2", "",
           "Plain spoken English. Each scene lists what is on screen, every spoken sentence (one sentence = one on-screen step, "
           "with its timestamp in `GeoLegalVault_Demo_v2.mp4`), the backend operation, the expected evidence and troubleshooting.", "",
           "The text under *Say* is what the synthetic voice reads (a few terms are respelled for the voice only, e.g. SHA-256). "
           "To record your own voice, read the same text over `GeoLegalVault_Demo_v2_silent_captions.mp4`.", "",
           "Always say: Ethereum **Sepolia testnet**, tamper-**evident**, policy-level geofencing, prototype. Never claim the system prevents "
           "tampering or promises a location. The app has no rejected state: say \"changes requested\".", ""]
    for sc in SCENES:
        ts = (timestamps or {}).get(sc["id"])
        out += [f"## {sc['title']}" + (f"  \n**Timestamp in final video:** {ts}" if ts else ""), "",
                f"- **On screen / page:** {sc['page']}", f"- **Action:** {sc['action']}", "", "**Say:**", ""]
        for key, text in sc["lines"]:
            t = (beat_times or {}).get((sc["id"], key))
            out.append(f"- {('`' + t + '` ') if t else ''}{text}")
        out += ["", f"- **Backend operation:** {sc['backend']}", f"- **Expected evidence:** {sc['evidence']}",
                f"- **Troubleshooting:** {sc['troubleshooting']}", ""]
    (HERE / "NARRATION_SCRIPT.md").write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    print("changed audio texts:", write_audio_texts())
    tot = 0
    for sc in SCENES:
        w = sum(len(t.split()) for _, t in sc["lines"])
        tot += w
        print(sc["id"], w, "words")
    print("TOTAL", tot, "words (~", round(tot / 2.5 / 60, 1), "min at 150 wpm )")
