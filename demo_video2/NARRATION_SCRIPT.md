# Narration script - GeoLegalVault demo v2

Plain spoken English. Each scene lists what is on screen, every spoken sentence (one sentence = one on-screen step, with its timestamp in `GeoLegalVault_Demo_v2.mp4`), the backend operation, the expected evidence and troubleshooting.

The text under *Say* is what the synthetic voice reads (a few terms are respelled for the voice only, e.g. SHA-256). To record your own voice, read the same text over `GeoLegalVault_Demo_v2_silent_captions.mp4`.

Always say: Ethereum **Sepolia testnet**, tamper-**evident**, policy-level geofencing, prototype. Never claim the system prevents tampering or promises a location. The app has no rejected state: say "changes requested".

## Scene 1 - The problem and the idea  
**Timestamp in final video:** 0:04 - 1:16

- **On screen / page:** Title card, then two slides (no application screen)
- **Action:** The problem; what GeoLegalVault does; what the next twenty minutes show.

**Say:**

- `0:04` Legal documents face two quiet risks.
- `0:07` First, a file can be changed after everyone agreed to it, and nobody notices.
- `0:13` Second, anyone with a login can upload or approve from anywhere.
- `0:18` GeoLegalVault is a prototype that tackles both.
- `0:21` Uploads and approvals are allowed only from an approved area. That area is called a geofence, a virtual boundary drawn on a map.
- `0:30` Every document is reviewed and approved by different people, so nobody approves their own work.
- `0:36` When a version is approved, a fingerprint of the file, called a SHA-256 hash, is written to the Ethereum Sepolia test network.
- `0:45` Later, anyone can recompute the fingerprint and see whether the file still matches. This is tamper-evident: changes are detected, not prevented.
- `0:55` In about twenty minutes we follow one fresh document through its whole life: upload, approval, anchoring, tampering, an amendment, a download, and archive.
- `1:05` Everything you will see is the real running system, on a test network. Where the screen cannot show something, like database records, I label it a supplementary view.

- **Backend operation:** None.
- **Expected evidence:** Slides only.
- **Troubleshooting:** None.

## Scene 2 - Login, roles, clearance and names  
**Timestamp in final video:** 1:16 - 2:25

- **On screen / page:** /login, then the Dashboard, for three users in three separate browser sessions
- **Action:** Authorized Staff, Legal Officer and Administrator each sign in; the welcome line shows a name; the counts differ by clearance.

**Say:**

- `1:16` First, login and roles. There are five roles: Administrator, Legal Officer, Reviewing Officer, Authorized Staff and Auditor. A role is a set of permissions.
- `1:28` Here Authorized Staff is signed in. The welcome line shows the person's name, not a database id. The menu has Upload, but no Admin Panel and no Audit Logs.
- `1:39` These counts come from the server, and they differ for each person. In total the vault holds twenty-one demo documents, two of them archived, and archived ones are left out of these counts.
- `1:50` Next, a Legal Officer signs in, in a completely separate browser session. This role has a higher clearance, so it sees more documents.
- `2:00` Then an Administrator. Their menu shows the Admin Panel and Audit Logs, but no Upload. Administrators manage users and zones, but they cannot upload, review or approve.
- `2:12` Every person also has a clearance level: Public, Internal, Confidential, Restricted or Top Secret. The menu is only a convenience. The server checks role and clearance on every single request.

- **Backend operation:** POST /api/v1/auth/login (auth/service.py); role, name and clearance come from the users collection on every request (core/rbac.py, core/clearance.py).
- **Expected evidence:** Different sidebars per role; the name in the welcome line; different document counts per person.
- **Troubleshooting:** Login fails: check that the demo backend is on port 8001 and the demo users were seeded (scripts/seed.py --demo). Never enter a wrong password more than twice on a real account.

## Scene 3 - Administrator: zones and users  
**Timestamp in final video:** 2:25 - 3:20

- **On screen / page:** /admin (Geofences tab, Users tab)
- **Action:** Admin views the zone, then creates a throwaway low-clearance user.

**Say:**

- `2:25` Now the Administrator's Admin Panel. The Geofences tab lists the approved zones.
- `2:31` A zone is a polygon: a list of longitude and latitude pairs, always in that order. The form previews the approximate centre of the ring you type, and asks the administrator to confirm the place. That preview is only a visual aid. Our demo zone, HQ Campus, is the small box listed below, around latitude eleven point six seven and longitude seventy-eight point one five. Every request is tested against it on the server.
- `2:58` Now the Users tab. People are shown by name, with their role and clearance.
- `3:04` We create a throwaway account with the Auditor role. A new user starts at the lowest clearance, Public, and the password field is masked.
- `3:13` The new account appears in the table. We will use it later, to show a hidden document and the login protection.

- **Backend operation:** GET/POST /api/v1/geofences, /api/v1/users (geofences/service.py, users/service.py).
- **Expected evidence:** Zone list; new user in the table with clearance Public.
- **Troubleshooting:** Create-user 409: the email already exists (the throwaway email carries the date).

## Scene 4 - Upload version one inside the zone  
**Timestamp in final video:** 3:20 - 4:47

- **On screen / page:** /documents/upload, /documents/<id>, /documents/<id>/versions, plus two supplementary views
- **Action:** Authorized Staff uploads DEMO-20261022-Lease (Internal) from inside the zone, sees Draft, then submits it.

**Say:**

- `3:20` Now the main flow, with one fresh document. Authorized Staff opens Upload. The page shows the location the browser reports. On a real device that comes from GPS or Wi-Fi. In this recording a test harness supplies it, and the label says so. The server still validates it.
- `3:39` We enter a title, the type Lease, the classification Internal, and pick a sample PDF.
- `3:46` On Upload, the server checks, in a fixed order: your token, your role, your location, then the file. Then it stores the file, computes the hash and writes an audit entry. The document is saved as a Draft, owned by Authorized Staff.
- `4:02` In this supplementary view, the real database shows the document row and the version row. The highlighted field is the SHA-256 fingerprint of the file. It turns any file into sixty-four characters, and changing one byte changes all of them.
- `4:17` The file itself is not in the database. It sits in private object storage, called RustFS here and Cloudflare R2 in production, under a server-made key that includes the hash. This demo shares one bucket with the development setup, but this document has its own object.
- `4:34` The uploader then submits the document for review, and the status becomes Submitted.
- `4:39` In the app, Version History shows the fingerprint, shortened. The full value is in the database.

- **Backend operation:** POST /api/v1/documents (documents/router.py) -> services/hashing.py -> services/storage.py put_object -> insert documents + document_versions -> audit UPLOAD; POST /documents/{id}/submit.
- **Expected evidence:** Status Draft then Submitted; version row with sha256 and storage_key; object listed in the bucket.
- **Troubleshooting:** GEOFENCE_DENIED: the user must have the zone assigned and the browser location must be inside it. 413: file over the size limit. MIME_MISMATCH: the content does not match the type.

## Scene 5 - Upload refused: outside the zone, and poor accuracy  
**Timestamp in final video:** 4:47 - 5:53

- **On screen / page:** /documents/upload with two different browser locations, then one supplementary view
- **Action:** Same user and form: first about 100 km outside the zone, then inside but with 500 m accuracy.

**Say:**

- `4:47` Now the negative cases. The same user tries again, but the browser reports a place about one hundred kilometres outside the zone.
- `4:55` The server answers GEOFENCE_DENIED, and nothing is stored. The server decides inside or outside, never the browser.
- `5:03` Now the location is inside the zone, but very imprecise: plus or minus five hundred metres.
- `5:10` The server refuses that too, with LOCATION_LOW_CONFIDENCE. This is called fail-closed: if the system is not sure, it says no. This server allows up to three hundred metres of uncertainty.
- `5:23` The zone denial is written to the audit log with the claimed position, as you can see here. The low-confidence refusal is different: it happens before the zone check, and it goes to the application log, not to the audit log.
- `5:36` An honest limit: browser location can be faked, for example with developer tools. So geofencing here is a policy control that adds a layer. It is not a guarantee of where someone is. The tamper-evidence comes from the blockchain, not from the geofence.

- **Backend operation:** services/geofence.py check_location: accuracy limit, then freshness, then a MongoDB point-in-polygon query against the user's assigned zones. LOCATION_LOW_CONFIDENCE 422, LOCATION_STALE 422, INVALID_LOCATION 422, GEOFENCE_DENIED 403.
- **Expected evidence:** Red banners with the error codes; audit_logs row GEOFENCE_DENIED.
- **Troubleshooting:** LOCATION_LOW_CONFIDENCE for a good reading: check GEO_ACCURACY_MAX_M (this machine uses 300) and that the right backend is on port 8001.

## Scene 6 - Review, maker-checker and approval  
**Timestamp in final video:** 5:53 - 7:15

- **On screen / page:** Document Details for three roles; one supplementary API view
- **Action:** A seeded self-approval attempt is refused; the Reviewing Officer reviews the lease; a different Legal Officer approves it inside the zone (transaction 1).

**Say:**

- `5:53` Next, review and approval. This uses maker-checker, meaning the person who made a document must not be the one who checks it.
- `6:01` Here a Legal Officer opens a seeded document that they uploaded themselves. There is no Approve button, and the page says someone else must approve it.
- `6:10` If they call the server directly anyway, from inside the zone, the answer is MAKER_CHECKER_VIOLATION. That is a real response, shown in a supplementary view. Nothing was changed.
- `6:22` Now the real path for our lease. A Reviewing Officer, a different person from the uploader, opens it and chooses Review.
- `6:30` They pass the review, and the status becomes Pending Approval. A reviewer can instead request changes, which sends it back to the uploader. This app has no rejected state.
- `6:42` Then a Legal Officer who did not upload it opens the document. The Approve button is there. The server checks the location first.
- `6:50` Approval starts anchoring automatically, and there is no anchor button. The backend's own wallet signs the transaction, never the user. This is a real transaction on the Sepolia test network, the free test version of Ethereum. I have trimmed the wait for the block.
- `7:08` The status becomes Active. The approval cost a tiny amount of test Ether, which has no real value.

- **Backend operation:** POST /documents/{id}/review (workflow.review); POST /documents/{id}/approve (geofenced; workflow.approve -> blockchain/service.py -> services/blockchain.py -> DocumentAnchor.anchor). Checks: RBAC approve:perform, geofence, enforce_maker_checker (before anything touches the chain).
- **Expected evidence:** Statuses Submitted -> Pending Approval -> Approved -> Active; HTTP 403 MAKER_CHECKER_VIOLATION.
- **Troubleshooting:** Document stays APPROVED: the transaction was not confirmed inside the request window and the optional anchor worker is not running. This recording raised ANCHOR_CONFIRM_POLL_ATTEMPTS for the backend process only.

## Scene 7 - What is anchored on Sepolia  
**Timestamp in final video:** 7:15 - 8:28

- **On screen / page:** /documents/<id>/versions, /versions/<id>/blockchain, Etherscan, one supplementary view
- **Action:** Open the anchor record: recorded hash and live on-chain hash side by side; then the public Etherscan page.

**Say:**

- `7:15` Now, what exactly went on the blockchain. In Version History, version one is Active and marked Confirmed. We open View on-chain.
- `7:24` The Blockchain Anchor Record puts two hashes side by side. On the left, the hash recorded in our database. On the right, the hash the app has just read live from the contract on the Sepolia testnet. They are identical, and the page says Match.
- `7:40` The page also shows the network label, Sepolia testnet, the contract address, and the transaction hash, with a Copy button.
- `7:49` The smart contract, DocumentAnchor, stores only four things per document version: the hash, the version number, an event type, and the block time. The PDF, its filename and any person's name are not on-chain, because a blockchain is public and permanent. The contract also refuses a second anchor for the same version.
- `8:10` On the public Etherscan page for the Sepolia testnet, the transaction shows Status: Success, and a tiny fee.
- `8:18` One service wallet in the backend signs every anchor. That is a trust assumption we come back to at the end. And there is no Merkle tree: each file gets one hash.

- **Backend operation:** GET /api/v1/blockchain/anchor/{version_id}; contract call getAnchor(documentId, version); contracts/contracts/DocumentAnchor.sol.
- **Expected evidence:** Anchor record: Match banner, two equal hashes, Sepolia testnet label, Copy button; Etherscan: Status Success.
- **Troubleshooting:** Etherscan page blank: network or the site's bot checks; the transaction hash is on the Anchor Record page.

## Scene 8 - Clearance: a hidden document is a 404  
**Timestamp in final video:** 8:28 - 9:33

- **On screen / page:** /documents and /documents/<id> as the Public-clearance user, then as the Administrator; two supplementary views
- **Action:** The throwaway user cannot see the Internal lease; the Administrator cannot open a seeded Confidential document.

**Say:**

- `8:28` Now clearance. The throwaway user has the lowest level, Public, and our lease is Internal.
- `8:35` In the repository the lease is simply not listed, because the server filters in the database query.
- `8:42` Opening its exact link shows the app's own wording: That item couldn't be found, or you don't have access to it.
- `8:49` In the supplementary view, the real document and a made-up id give exactly the same answer, 404 not found. We use 404 instead of 403, which means forbidden, because a 403 would confirm that the document exists.
- `9:05` The same rule applies to everyone. Here the Administrator, whose clearance is Internal, opens a seeded document classified Confidential, and also gets a real 404. Administrators manage the system, but get no automatic access to document content.
- `9:21` A refused attempt on a document that exists is still written to the audit log as ACCESS_DENIED, as highlighted. This is access control inside the application. It is not encryption.

- **Backend operation:** documents/access.py load_visible_document and core/clearance.py can_see; audit action ACCESS_DENIED.
- **Expected evidence:** Empty search result; 'couldn't be found' banner; two identical 404 bodies; ACCESS_DENIED audit rows.
- **Troubleshooting:** If the page spins for several seconds before the message, the UI is retrying the 404 request.

## Scene 9 - Verify the genuine file: VERIFIED  
**Timestamp in final video:** 9:33 - 10:06

- **On screen / page:** /verify/<versionId>
- **Action:** Legal Officer clicks Run verification.

**Say:**

- `9:33` Now the core feature: verification. The Legal Officer opens Integrity Verification for version one.
- `9:40` When we run it, the server reads the stored file and recomputes its SHA-256. It compares that with the hash saved in the database at upload, and with the anchored hash it reads live from the Sepolia contract.
- `9:53` All three are identical, so the result is VERIFIED.
- `9:57` A database change alone, or a storage change alone, cannot produce a false VERIFIED, because the chain holds the original value.

- **Backend operation:** POST /api/v1/verify/{version_id} (verify/service.py): storage get_object, sha256, MongoDB document_versions.sha256, contract getAnchor; inserts a verification_records row and an audit row.
- **Expected evidence:** Green VERIFIED banner; three equal hashes.
- **Troubleshooting:** CHAIN_UNREACHABLE: the Sepolia RPC could not be read; no verdict is given.

## Scene 10 - Tamper with the stored file, restore it, clear the flag  
**Timestamp in final video:** 10:06 - 11:34

- **On screen / page:** Supplementary views, /verify/<versionId>, Document Details as Legal Officer and as Administrator
- **Action:** Save the original bytes; demo/tamper.py changes one byte of this document's own object; verify (MISMATCH); restore and confirm the hash; verify (VERIFIED); the Administrator clears the flag.

**Say:**

- `10:06` Now the attack. First, for the demo, I save a copy of the original file bytes locally, and check that their hash equals the recorded fingerprint. That lets me put things back afterwards.
- `10:18` Now someone with direct access to the storage server changes one byte of the file, not through the app. This script bypasses the application on purpose, and it touches only this document's own object. The database and the blockchain still hold the original hash.
- `10:34` We run verification again. The result is MISMATCH, tamper detected. The recomputed hash is completely different, while the stored and on-chain hashes still agree. One changed byte gives a totally different hash. That is called the avalanche effect.
- `10:50` The document is also flagged as Tampered. The system made the change evident. It did not prevent it.
- `10:57` Now I write the original bytes back to the same storage key, and confirm that their hash matches the recorded SHA-256.
- `11:05` Verification returns to VERIFIED.
- `11:09` But the Tampered flag is still on the document. A later pass does not clear it automatically.
- `11:15` Only an Administrator can clear it. They choose Clear integrity flag, and must give a reason of at least ten characters, which is written to the audit log.
- `11:25` The app re-runs verification on every anchored version first, and only then clears the flag. The flag is gone, and the document is clean again.

- **Backend operation:** demo/tamper.py (put_object with byte 0 changed, latest version only); POST /verify/{id} -> MISMATCH -> documents.integrity_flag = TAMPERED and audit VERIFY_FAIL; POST /documents/{id}/integrity/clear (Administrator, reason >= 10 chars) -> INTEGRITY_CLEARED.
- **Expected evidence:** Red MISMATCH banner; Tampered badge; verification history MISMATCH then VERIFIED; flag cleared by the Administrator.
- **Troubleshooting:** Run tamper.py only with MONGODB_DB=geolegalvault_demo and the exact title. To restore, write the saved original bytes back to the same storage key (work/ folder).

## Scene 11 - Amendment: version two  
**Timestamp in final video:** 11:34 - 13:48

- **On screen / page:** Document Details, /documents/<id>/amend, /documents/<id>/versions, /versions/<id>/blockchain, /verify/<id>
- **Action:** Request amendment (Legal Officer); upload V2 (Authorized Staff); submit; review; approve (transaction 2); Version History; proof of the hash link; verify V2 and V1.

**Say:**

- `11:34` Now an amendment, which creates version two. Documents are never edited in place. Each version is a new, immutable record.
- `12:10` A Legal Officer opens the active lease and chooses Request amendment. This is geofenced, so the location is checked.
- `12:18` They must give a reason. The document moves to Amendment Requested.
- `12:23` Now Authorized Staff uploads the amended file, version two. The title, type and classification are copied from the document and cannot change.
- `12:33` Version two starts as a Draft, and its uploader submits it.
- `12:37` The three-person rule applies again. The Reviewing Officer reviews version two.
- `12:43` And the Legal Officer, who did not upload it, approves. This sends a second real transaction on the Sepolia test network, for version two. Again I trim the wait.
- `12:56` In Version History, version two is Active and Confirmed. Version one now carries the grey Superseded badge. That is the only place the app says so. There is no separate current label: the Active badge marks the current version.
- `13:11` The hashes are shortened on that page, so this supplementary view shows the proof. The previous-hash field of version two equals, character for character, the SHA-256 of version one. There is no parent version id field. This hash link is the connection.
- `13:28` Version two has its own anchor, again with the recorded and on-chain hashes side by side, and a Match.
- `13:34` Verification of version two returns VERIFIED.
- `13:38` And version one still verifies, because its file, its hash and its anchor are untouched. The Verification page does not mention superseded at all.

- **Backend operation:** POST /documents/{id}/amend (geofenced) -> AMENDMENT_REQUESTED; POST /documents with amend_of (geofenced) -> create_next_version (version_no 2, prev_version_hash = V1 sha256); submit/review/approve act on the highest version_no; complete_promotion marks V1 SUPERSEDED when V2 is ACTIVE.
- **Expected evidence:** Version History: V2 ACTIVE + CONFIRMED, V1 grey SUPERSEDED; prev_version_hash equals V1 sha256; two anchors; both versions VERIFIED.
- **Troubleshooting:** V2 stays APPROVED: the anchor did not confirm in the request window; stop, do not start the worker for the recording.

## Scene 12 - Download the current version  
**Timestamp in final video:** 13:48 - 14:43

- **On screen / page:** Document Details (Download), two supplementary views, a refused download
- **Action:** Download (geofenced, current version only); hash of the downloaded bytes equals the recorded SHA-256; ACCESS audit row; outside the zone and below clearance are refused.

**Say:**

- `13:48` Now download. The Download button gives the current version only, which is now version two. It is geofenced, so the location is checked first.
- `13:58` The server answers with a short-lived pre-signed link, valid for sixty seconds. The file never passes through the API. I will not show the link itself on screen.
- `14:09` To prove the download is genuine, the test harness fetched the file through that link and hashed it. The result equals the recorded SHA-256 of version two.
- `14:19` The download is audited as ACCESS, with the version id, as highlighted.
- `14:24` Now the real denials. From outside the zone, the same Download button is refused with GEOFENCE_DENIED.
- `14:32` And a below-clearance viewer who is inside an assigned zone gets a 404 for the same document, so the file is never even offered. The order of checks is the zone first, then clearance.

- **Backend operation:** GET /api/v1/documents/{id}/download (geofenced; documents/router.py -> storage.generate_presigned_get, TTL 60 s; audit ACCESS with meta.version_id).
- **Expected evidence:** Hash of downloaded bytes = documents version sha256; ACCESS audit row; GEOFENCE_DENIED banner; 404 for the Public viewer.
- **Troubleshooting:** The UI opens the pre-signed URL in a new tab; the recording captures it without displaying it. Download shows the current version only (V1 before V2 is Active).

## Scene 13 - Archive  
**Timestamp in final video:** 14:43 - 15:26

- **On screen / page:** Document Details (Archive), Dashboard, Document Repository (default and Archived filter)
- **Action:** Legal Officer archives the fresh document from Active.

**Say:**

- `14:43` Finally, the end of the lifecycle: archive. The lease is Active, and it is in the repository list.
- `14:51` The Legal Officer opens it and chooses Archive. There is no reason field, and it is not geofenced.
- `14:58` The status is now Archived.
- `15:01` It has disappeared from the default Dashboard and Repository.
- `15:07` It appears when we filter the Repository on Archived.
- `15:11` Archiving keeps every version, anchor and file untouched. The Reports panel will count one more archived document. And the backend has no way to undo an archive: there is no restore route. Only direct database editing could change it.

- **Backend operation:** POST /api/v1/documents/{id}/archive (no body, not geofenced; ACTIVE only; Administrator or Legal Officer); audit ARCHIVE.
- **Expected evidence:** Status Archived; absent from default Repository; present under the Archived filter.
- **Troubleshooting:** 409 ILLEGAL_TRANSITION: only an Active document can be archived.

## Scene 14 - The other verification outcomes  
**Timestamp in final video:** 15:26 - 16:22

- **On screen / page:** /verify/<versionId> for a seeded draft, then one slide
- **Action:** Verify a seeded draft that was never approved: NOT_ANCHORED. One slide lists all six outcomes.

**Say:**

- `15:26` There are six possible verification results. One more, live: a seeded draft that was never approved.
- `15:34` The result is NOT ANCHORED. The file is intact, but there is no blockchain record to compare with. That is not an error and not an alarm.
- `15:43` Here are all six outcomes.
- `15:46` VERIFIED: the stored file, the recorded hash and the on-chain hash all agree. MISMATCH: the file differs from the record, which we saw.
- `15:56` NOT_ANCHORED: it was never approved, so there is nothing on-chain to compare, which we just saw.
- `16:03` ANCHOR_MISSING: the database says it was anchored, but the chain says no. FILE_MISSING: the stored file is gone. And CHAIN_UNREACHABLE: the blockchain could not be read, so there is no verdict at all.
- `16:16` I did not trigger those last three live. They are marked on the slide as not triggered live.

- **Backend operation:** verify/service.py verdict table.
- **Expected evidence:** Grey NOT ANCHORED banner; on-chain value 'not available'.
- **Troubleshooting:** None.

## Scene 15 - Login protection  
**Timestamp in final video:** 16:22 - 16:59

- **On screen / page:** /login (throwaway account only), one supplementary view
- **Action:** Five wrong passwords on the throwaway account: Attempt 1 of 5 ... 5 of 5, then the lockout message.

**Say:**

- `16:22` Login also has protection. On the throwaway account only, I type wrong passwords on purpose.
- `16:29` The page counts the attempts. Attempt one of five.
- `16:34` Attempt two.
- `16:36` Attempt three.
- `16:38` Attempt four.
- `16:40` Attempt five. Sign-in is now paused for about a minute.
- `16:45` The next try is refused outright: too many attempts. That slows down password guessing.
- `16:52` In MongoDB, the login_rate_limits collection holds the counter for each email, and when the pause ends.

- **Backend operation:** POST /auth/login failure path; lockout counter in the login_rate_limits collection (auth/service.py).
- **Expected evidence:** Attempt 1 of 5 ... Attempt 5 of 5; 'Too many attempts' message; login_rate_limits row.
- **Troubleshooting:** The lockout lasts about one minute; wait before logging in as that account.

## Scene 16 - Audit log, MongoDB and storage  
**Timestamp in final video:** 16:59 - 18:34

- **On screen / page:** /audit as Auditor (filters), Document Details, three supplementary views
- **Action:** Audit Logs at the top; action dropdown, actor search, document filter, View audit trail; then the real collections, id links and bucket.

**Say:**

- `16:59` Finally, where everything lives. The Auditor opens Audit Logs, and it opens at the top, newest first. Every action is a row: who, what, to what, and the result. Rows are only ever added.
- `17:13` The Action dropdown lists every action the log really contains. Here I pick Approve.
- `17:19` Actor search finds people by name or email. Here, Legal.
- `17:25` The document filter finds a document by its title, only among documents this person may open. Here, a seeded board resolution, and its trail.
- `17:35` For our lease, the same view is one click from the document page: View audit trail.
- `17:41` This is the whole life of the lease, with names instead of ids. The ids are secondary text underneath.
- `17:48` Next, the MongoDB collections. Users, geofences, documents and document versions are the authoritative data. The anchors collection is derived, because the chain is the real evidence. Verification records and audit logs are history.
- `18:04` The ids link them: a version points to its document, an anchor points to its version, and the storage key points to the file.
- `18:12` And the split: MongoDB holds state, fingerprints and audit. The private bucket holds the file bytes. The Sepolia contract holds the hash, version, event type and time.
- `18:24` One honest gap: the audit log has no hash chain yet, so someone with database write access could alter it. That is a planned improvement.

- **Backend operation:** GET /api/v1/audit and /audit/actions (audit/service.py); supplementary views are read-only pymongo and S3 list calls with secrets removed.
- **Expected evidence:** Audit table with names; filtered trail for the lease; JSON documents; bucket listing.
- **Troubleshooting:** Audit page empty: the account needs the audit:view permission (Auditor or Administrator).

## Scene 17 - Reports  
**Timestamp in final video:** 18:34 - 19:05

- **On screen / page:** /admin, Reports tab, as Auditor
- **Action:** The Reports panel; the count note; end on Mismatches and the archived count.

**Say:**

- `18:34` The Reports panel gives the whole picture. The Auditor can open it too.
- `18:39` Anchors confirmed counts the successful transactions, including our two.
- `18:44` This note reconciles the counts. The Auditor can access twenty-two documents in total, including three archived. The Dashboard and Repository show nineteen, because they leave archived documents out.
- `18:57` Mismatches counts our tamper test, and the archived count went up by one, because we archived the lease.

- **Backend operation:** GET /api/v1/reports/summary (reports/service.py), clearance-filtered.
- **Expected evidence:** Mismatches card >= 1; 'including 3 archived' note; ARCHIVED bar.
- **Troubleshooting:** Counts depend on the viewer's clearance: an Administrator at Internal sees fewer.

## Scene 18 - Summary and future work  
**Timestamp in final video:** 19:05 - 20:24

- **On screen / page:** Four slides
- **Action:** Components; honest limits; future work; the planned next version.

**Say:**

- `19:05` To summarise the parts. The front end is React. The back end is FastAPI in Python. MongoDB stores the data. RustFS in development, and Cloudflare R2 in production, store the files. web3.py talks to a Solidity smart contract on the Sepolia test network. Docker runs the services, and a CI pipeline runs the tests.
- `19:29` Honest limits. This is a prototype on a test network. Geofencing is a policy control, not proof of where someone is. A single service wallet signs every anchor. The audit log has no hash chain yet. There is one SHA-256 per file, with no Merkle tree. And verification detects tampering; it does not prevent it.
- `19:52` Future work includes the open items in the project's own tracker: stronger login and secret handling, called SEC-01 and SEC-03; deployment hardening, OPS-01; a hash chain for the audit log, CMP-01; and malware scanning of uploads. Also per-matter access, so that clearance can say this matter only, and richer display names.
- `20:15` There is also a planned next version that reduces how much you must trust the single service wallet. I won't describe its design here. Thank you.

- **Backend operation:** None.
- **Expected evidence:** Slides only.
- **Troubleshooting:** None.
