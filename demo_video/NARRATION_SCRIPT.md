# Narration script - GeoLegalVault demo

Plain spoken English. Each scene lists what is on screen, what to say before / during / after, the backend operation, the expected evidence and troubleshooting.
The text under *Say* is exactly what the synthetic voice reads. To record your own voice, read the same text over `GeoLegalVault_Demo_silent_captions.mp4`.
Always say: Ethereum **Sepolia testnet**, tamper-**evident**, policy-level geofencing, prototype. Never claim the system prevents tampering or guarantees a location.

## Scene 1 - The problem and the idea  
**Timestamp in final video:** 0:05 - 1:10

- **On screen / page:** Title slides (no application screen)
- **Action:** Two slides: the problem, and what GeoLegalVault does.

**Say before:** Legal documents face two quiet risks.

**Say during:** First, a file can be changed after everyone agreed to it, and nobody notices. Second, anyone with a login can upload or approve from anywhere. GeoLegalVault is a prototype that tackles both. Uploads and approvals are allowed only from an approved area. That area is called a geofence, a virtual boundary drawn on a map. Every document is reviewed and approved by different people, so nobody approves their own work. When a version is approved, a fingerprint of the file, called a SHA-256 hash, is written to the Ethereum Sepolia test network. Later, anyone can recompute the fingerprint and see whether the file still matches.

**Say after:** This is tamper-evident, which means changes are detected. It does not prevent changes. Everything you will see is the real running system. Where the screen cannot show something, like database records, I label it a supplementary view.

- **Backend operation:** None.
- **Expected evidence:** Slides only.
- **Troubleshooting:** None.

## Scene 2 - Login, roles and clearance  
**Timestamp in final video:** 1:10 - 2:11

- **On screen / page:** /login, then Dashboard, for three different users in three separate browser sessions
- **Action:** Authorized Staff, Legal Officer and Administrator each sign in.

**Say before:** First, login and roles. There are five roles: Administrator, Legal Officer, Reviewing Officer, Authorized Staff and Auditor. A role is a set of permissions.

**Say during:** Here Authorized Staff is signed in. The menu has Upload, but no Admin Panel and no Audit Logs. Next, a Legal Officer signs in, in a completely separate browser session. Then an Administrator. Their menu shows the Admin Panel and Audit Logs, but no Upload. Administrators manage users and zones, but they cannot upload, review or approve. That separation of duties is deliberate.

**Say after:** Each user also has a clearance level: Public, Internal, Confidential, Restricted or Top Secret. Clearance decides which documents a person may see. The menu is only a convenience. The server checks role and clearance on every single request.

- **Backend operation:** POST /api/v1/auth/login (auth/service.py); role and clearance are read from the users collection on every request (core/rbac.py, core/clearance.py).
- **Expected evidence:** Different sidebars per role; role shown top right.
- **Troubleshooting:** Login fails: check that the backend is on port 8000 and the user was seeded (scripts/seed.py --demo). Never enter a wrong password more than twice on a real account.

## Scene 3 - Administrator: zones and users, and login protection  
**Timestamp in final video:** 2:11 - 3:13

- **On screen / page:** /admin (Geofences tab, Users tab), then /login
- **Action:** Admin views the zone list, creates a throwaway low-clearance user; then five wrong passwords on that throwaway account.

**Say before:** Now the Administrator's Admin Panel, which has Users, Geofences, Reports and System Health.

**Say during:** The Geofences tab lists the zones. A zone is a polygon, a shape made of longitude and latitude points. Our demo zone, HQ Campus, is a small box around latitude 11.67 and longitude 78.15. Every request is tested against it on the server. Now the Users tab. We create a throwaway account with the Auditor role. A new user starts at the lowest clearance, Public, and the password field is masked. We will use this account later. Login also has protection. On this throwaway account only, I type wrong passwords on purpose.

**Say after:** After five failures the account is locked for a short time, and the next attempt is refused with: Too many attempts. That slows down password guessing.

- **Backend operation:** GET/POST /api/v1/geofences, /api/v1/users (geofences/service.py, users/service.py); lockout counter in the login_rate_limits collection (auth/service.py).
- **Expected evidence:** Polygon list; new user in the table with clearance Public; red 'Too many attempts' banner.
- **Troubleshooting:** Create-user 409: the email already exists. The lockout lasts one minute; wait before logging in as that account.

## Scene 4 - Upload inside the zone  
**Timestamp in final video:** 3:13 - 4:47

- **On screen / page:** /documents/upload, /documents/<id>, /documents/<id>/versions, plus two supplementary views
- **Action:** Authorized Staff uploads a sample lease PDF from inside the zone, sees status Draft, then submits it. Version History shows the fingerprint.

**Say before:** Now the main flow. Authorized Staff opens Upload. The page shows the location the browser reports. On a real device that comes from the browser's GPS or Wi-Fi location. In this recording a test harness supplies it, and the label says so. The server still validates it.

**Say during:** This location is inside the HQ zone. We enter a title, a type, the classification Confidential, and pick a sample PDF. On Upload, the server checks, in a fixed order: your token, your role, your location, then the file. Then it stores the file, computes the hash and writes an audit entry. The document is saved as a Draft. In this supplementary view, the real database shows the document row, and the version row with the SHA-256 fingerprint. The file itself is not in the database. It sits in private object storage, called RustFS here and Cloudflare R2 in production, under a server-made key that includes the hash. The uploader then submits it for review, and the status becomes Submitted. In the app, Version History shows the fingerprint, shortened. A SHA-256 hash turns any file into 64 characters, and changing one byte changes all of them.

**Say after:** The bucket listing confirms the stored object. The bucket is private. Downloads use a link that expires in sixty seconds.

- **Backend operation:** POST /api/v1/documents (documents/router.py) -> services/hashing.py -> services/storage.py put_object -> insert documents + document_versions -> audit UPLOAD; POST /documents/{id}/submit.
- **Expected evidence:** Status Draft then Submitted; version row with sha256 and storage_key; object listed in the bucket.
- **Troubleshooting:** GEOFENCE_DENIED: the user must have the zone assigned and the browser location must be inside it. 413: file over 10 MB. MIME_MISMATCH: the file content does not match its type.

## Scene 5 - Upload refused: outside the zone, and poor accuracy  
**Timestamp in final video:** 4:47 - 5:52

- **On screen / page:** /documents/upload with two different browser locations
- **Action:** Same user, same form. First the location is about 100 km outside the zone; then inside, but with a 500 metre accuracy.

**Say before:** Now the negative cases. The same user tries again, but the browser reports a place about 100 kilometres outside the zone.

**Say during:** The server answers GEOFENCE_DENIED, and nothing is stored. The server decides inside or outside, never the browser. Now the location is inside the zone, but very imprecise: plus or minus 500 metres. The server refuses that too, with LOCATION_LOW_CONFIDENCE. This is called fail-closed: if the system is not sure, it says no. This machine allows up to 300 metres of uncertainty. In the supplementary view, the zone denial is written to the audit log with the claimed position.

**Say after:** An honest limit: browser location can be faked, for example with developer tools. So geofencing here is a policy control that adds a layer. It is not a guarantee. The tamper-evidence comes from the blockchain, not from the geofence.

- **Backend operation:** services/geofence.py check_location: accuracy limit, then freshness (age of the reading), then a MongoDB point-in-polygon query against the user's assigned zones. Errors: LOCATION_LOW_CONFIDENCE 422, LOCATION_STALE 422, INVALID_LOCATION 422, GEOFENCE_DENIED 403.
- **Expected evidence:** Red banners with the error codes; audit_logs row GEOFENCE_DENIED.
- **Troubleshooting:** LOCATION_LOW_CONFIDENCE for a good reading: another backend may be on port 8000 or the accuracy limit differs. This machine uses GEO_ACCURACY_MAX_M=300 and GEO_FRESHNESS_MAX_SEC=120.

## Scene 6 - Review, maker-checker, and approval  
**Timestamp in final video:** 5:52 - 7:12

- **On screen / page:** Document Details for three roles; one supplementary API view
- **Action:** A Reviewing Officer reviews; the uploader's self-approval is refused; a different Legal Officer approves inside the zone.

**Say before:** Next, review and approval. This uses maker-checker, meaning the person who made a document must not be the one who checks it.

**Say during:** A Legal Officer uploads a second document, Doc B, and submits it. A Reviewing Officer, a different person, reviews and passes it. Back as the uploader, the Legal Officer has no Approve button. If they call the server directly anyway, from inside the zone, the answer is: MAKER_CHECKER_VIOLATION. That is a real response, shown in a supplementary view. Now for the main lease. The same Reviewing Officer passes it, and it becomes Pending Approval. Then a Legal Officer who did not upload it clicks Approve. The location is checked first. Approval starts anchoring automatically, and there is no anchor button. The backend's own wallet signs the transaction, never the user. This is a real transaction on the Sepolia test network, the free test version of Ethereum. We wait for it to be included in a block. The status becomes Active.

**Say after:** Approval spent a tiny amount of test Ether, about five trillionths of one Ether. Test Ether has no real value.

- **Backend operation:** POST /documents/{id}/review (workflow.review), POST /documents/{id}/approve (geofenced; workflow.approve -> blockchain/service.py -> services/blockchain.py -> DocumentAnchor.anchor). Checks: RBAC approve:perform, geofence, enforce_maker_checker.
- **Expected evidence:** Statuses Submitted -> Pending Approval -> Approved -> Active; HTTP 403 MAKER_CHECKER_VIOLATION.
- **Troubleshooting:** Document stays APPROVED: the transaction was not confirmed inside the request window and the optional anchor worker is not running. This recording raised ANCHOR_CONFIRM_POLL_ATTEMPTS for the backend process only.

## Scene 7 - What is anchored on Sepolia  
**Timestamp in final video:** 7:12 - 8:12

- **On screen / page:** /documents/<id>/versions, /versions/<id>/blockchain, Etherscan, one supplementary view
- **Action:** Open the anchor record, read the live on-chain value, then the public Etherscan page.

**Say before:** Now, what exactly went on the blockchain.

**Say during:** The Blockchain Anchor Record shows the network, sepolia, the contract address, the transaction hash and the block number. Below it, the app asks the contract live, and the on-chain hash equals the recorded hash. The smart contract, DocumentAnchor, stores only four things per document version: the hash, the version number, an event type, and the block time. The PDF, its filename and any person's name are not on-chain. A blockchain is public and permanent, so we keep confidential content off it. The contract also refuses a second anchor for the same version. On the public Etherscan page, the transaction shows Success on the Sepolia testnet, with a tiny fee.

**Say after:** One service wallet in the backend signs every anchor. There is no Merkle tree: each file gets one hash.

- **Backend operation:** GET /api/v1/blockchain/anchor/{version_id}; contract call getAnchor(documentId, version); contracts/contracts/DocumentAnchor.sol.
- **Expected evidence:** Anchor record fields; Etherscan: Status Success, a Sepolia Testnet banner.
- **Troubleshooting:** Etherscan page blank: network or the site's bot checks; the transaction hash is on the Anchor Record page.

## Scene 8 - Clearance: a hidden document is a 404  
**Timestamp in final video:** 8:12 - 9:01

- **On screen / page:** /documents (repository) and /documents/<id> as the Public-clearance user
- **Action:** The throwaway user searches and then opens the exact link.

**Say before:** Now clearance. The throwaway Auditor has the lowest level, Public, and the lease is Confidential.

**Say during:** In the repository the lease is simply not listed, because the server filters in the database query. Opening its exact link shows: that item couldn't be found. In the supplementary view, the real document and a made-up id give the same answer, 404 not found. We use 404 instead of 403, which means forbidden, because a 403 would confirm that the document exists.

**Say after:** The refused attempt on the real document is still written to the audit log as ACCESS_DENIED. This is access control inside the application. It is not encryption.

- **Backend operation:** documents/access.py load_visible_document and core/clearance.py can_see; audit action ACCESS_DENIED.
- **Expected evidence:** Empty search result; 'couldn't be found' banner; two identical 404 bodies.
- **Troubleshooting:** If the page spins for several seconds before the message, the UI is retrying the 404 request.

## Scene 9 - Verify the genuine file: VERIFIED  
**Timestamp in final video:** 9:01 - 9:36

- **On screen / page:** /verify/<versionId>
- **Action:** Legal Officer clicks Run verification.

**Say before:** Now the core feature: verification.

**Say during:** When we run it, the server does three things in order. It reads the stored file and recomputes its SHA-256. It compares that with the hash saved in the database at upload. And it reads the anchored hash from the Sepolia contract, live. All three are identical, so the result is VERIFIED.

**Say after:** A database change alone, or a storage change alone, cannot produce a false VERIFIED, because the chain holds the original value.

- **Backend operation:** POST /api/v1/verify/{version_id} (verify/service.py): storage get_object, sha256, MongoDB document_versions.sha256, contract getAnchor; inserts a verification_records row and an audit row.
- **Expected evidence:** Green VERIFIED banner; three equal hashes.
- **Troubleshooting:** CHAIN_UNREACHABLE: the Sepolia RPC could not be read; no verdict is given.

## Scene 10 - Tamper with the stored file: MISMATCH  
**Timestamp in final video:** 9:36 - 10:34

- **On screen / page:** Terminal-style supplementary view, then /verify/<versionId> and Document Details
- **Action:** demo/tamper.py changes one byte of the stored object; verification is run; the original bytes are then restored and verification is run again.

**Say before:** Now the attack. Someone with direct access to the storage server changes one byte of the file, not through the app.

**Say during:** This script bypasses the application on purpose. The database and the blockchain still hold the original hash. We run verification again. The result is MISMATCH, tamper detected. The recomputed hash is completely different, while the stored and on-chain hashes still agree. One changed byte gives a totally different hash. That is called the avalanche effect. The document is also flagged. For the dev data, I then write the original bytes back to the same storage key, and verification returns to VERIFIED.

**Say after:** Notice what the system did: it made the change evident. It did not prevent it. The integrity flag stays until an Administrator clears it, and clearing it re-runs the three checks first.

- **Backend operation:** demo/tamper.py (put_object with byte 0 changed); POST /verify/{id} -> MISMATCH -> documents.integrity_flag = TAMPERED and audit VERIFY_FAIL.
- **Expected evidence:** Red MISMATCH banner; verification history shows VERIFIED, MISMATCH, VERIFIED.
- **Troubleshooting:** Run tamper.py only after the version is Active, with the exact title. To restore, write the original file bytes back to the same storage key.

## Scene 11 - Other verification outcomes  
**Timestamp in final video:** 10:34 - 11:22

- **On screen / page:** /verify/<versionId> for Doc B, then a slide
- **Action:** Verify Doc B, which was never approved: NOT_ANCHORED. A slide lists the other outcomes.

**Say before:** There are six possible results. Here is one more, live.

**Say during:** Doc B passed review but was never approved, so nothing was anchored. The result is NOT ANCHORED. The file is intact, but there is no blockchain record to compare with. That is not an error and not an alarm.

**Say after:** The remaining outcomes are on this slide. MISMATCH, which we saw. ANCHOR_MISSING: the database says it was anchored but the chain says no. FILE_MISSING: the stored file is gone. And CHAIN_UNREACHABLE: the blockchain could not be read, so there is no verdict at all. I did not trigger those three live, because that would break the dev setup.

- **Backend operation:** verify/service.py verdict table (D-049).
- **Expected evidence:** Grey NOT ANCHORED YET banner; on-chain value 'not available'.
- **Troubleshooting:** None.

## Scene 12 - Audit log, MongoDB and storage  
**Timestamp in final video:** 11:22 - 12:39

- **On screen / page:** /audit as Auditor, then three supplementary views
- **Action:** Show the audit log, then the real collections, the id links and the bucket.

**Say before:** Finally, where everything lives. The Auditor opens the Audit Logs page.

**Say during:** Every action is a row: who, what, to what, and the result. Rows are only ever added. In the first supplementary view, these are the audit rows for our lease: upload, submit, review, approve, anchor confirmed, activate, and the verify results. Next, the MongoDB collections. Users, geofences, documents and document versions are the authoritative data. The anchors collection is derived, because the chain is the real evidence. Verification records and audit logs are history. The ids link them: a version points to its document, an anchor points to its version, and the storage key points to the file. Last, the split. MongoDB holds state, fingerprints and audit. The private bucket holds the file bytes. The Sepolia contract holds the hash, version, event type and time.

**Say after:** One honest gap: the audit log has no hash chain yet, so someone with database write access could alter it. That is a planned improvement.

- **Backend operation:** GET /api/v1/audit (audit/service.py); supplementary views are read-only pymongo and S3 list calls with secrets removed.
- **Expected evidence:** Audit table; JSON documents; bucket listing.
- **Troubleshooting:** Audit page empty: the account needs the audit:view permission (Auditor or Administrator).

## Scene 13 - Components and future work  
**Timestamp in final video:** 12:39 - 13:36

- **On screen / page:** Two slides
- **Action:** Summary of the parts, and what is planned.

**Say before:** To summarise the parts.

**Say during:** The front end is React. The back end is FastAPI in Python. MongoDB stores the data. RustFS in development, and Cloudflare R2 in production, store the files. web3.py talks to a Solidity smart contract on the Sepolia test network. Docker runs the services, and a CI pipeline runs the tests.

**Say after:** Future work includes the open items in the project's own tracker: stronger login and secret handling, deployment hardening, a hash chain for the audit log, and malware scanning of uploads. There is also a planned next version that reduces how much you must trust the single service wallet. I won't describe its design here. Not demonstrated: document amendment with a second version, and the optional anchor worker. Thank you.

- **Backend operation:** None.
- **Expected evidence:** Slides only.
- **Troubleshooting:** None.
