"""Speaker wording for the silent demo video: sid -> [(on-screen cue, [(beat key, spoken text)])].

Same beats and order as narration.py / captions.srt; sentences are trimmed so each can be said at 130 words per
minute or less inside the time the video gives it (make_speaker_script.py checks this). Code names are written the way
they are spoken ("geofence denied" for GEOFENCE_DENIED); make_speaker_script.py adds the pronunciation hints.
"""

C = {
"s01": [
 ("Title card, then Slide 1: the problem", [
  ("a1", "Legal documents face two quiet risks."),
  ("a2", "First, a file can be changed after everyone agreed, unnoticed."),
  ("a3", "Second, any login works from anywhere.")]),
 ("Slide 2: what GeoLegalVault does", [
  ("b1", "GeoLegalVault is a prototype tackling both."),
  ("b2", "Uploads and approvals are allowed only inside an approved area, called a geofence, a virtual boundary."),
  ("b3", "Different people review and approve, so nobody approves their own work."),
  ("b4", "Once approved, a fingerprint of the file, a SHA-256 hash, is written to the Ethereum Sepolia test network."),
  ("b5", "Anyone can recompute the fingerprint later and check the file. This is tamper-evident: changes are detected, not prevented."),
  ("b6", "In about twenty minutes we follow one document through its whole life: upload, approval, anchoring, tampering, amendment, download, archive."),
  ("b7", "Everything is the real system on a test network. Where the screen can't show something, I label it a supplementary view.")]),
],
"s02": [
 ("Login page, then the Dashboard as Authorized Staff", [
  ("k1", "First, login and roles. There are five: Administrator, Legal Officer, Reviewing Officer, Authorized Staff, and Auditor. A role is a set of permissions."),
  ("k2", "Authorized Staff is signed in. The welcome line shows a name. The menu has Upload, but no Admin Panel or Audit Logs."),
  ("k3", "These counts come from the server and differ per person. The vault holds twenty-one demo documents, two archived, which these counts leave out.")]),
 ("A second browser session: Legal Officer, then Administrator", [
  ("k4", "Next, a Legal Officer signs in, in a separate browser session. Higher clearance, so more documents."),
  ("k5", "Then an Administrator. Their menu has Admin Panel and Audit Logs, no Upload. Administrators manage users and zones; they cannot upload, review or approve."),
  ("k6", "Everyone also has a clearance level: Public, Internal, Confidential, Restricted or Top Secret. The menu is a convenience; the server checks role and clearance on every request.")]),
],
"s03": [
 ("Admin Panel, Geofences tab", [
  ("k1", "Now the Administrator's Admin Panel. The Geofences tab lists approved zones."),
  ("k2", "A zone is a polygon of longitude and latitude pairs, always in that order. The form previews the centre, as a visual aid only. Our demo zone, HQ Campus, is the small box below, near latitude eleven point six seven, longitude seventy-eight point one five. The server tests every request against it.")]),
 ("Admin Panel, Users tab: creating the throwaway user", [
  ("k3", "Now the Users tab: people shown by name, role and clearance."),
  ("k4", "We create a throwaway Auditor account. A new user starts at Public clearance, and the password is masked."),
  ("k5", "The new account appears. We use it later, for hidden documents and login limits.")]),
],
"s04": [
 ("Upload page as Authorized Staff", [
  ("k1", "Now the main flow, with one fresh document. Authorized Staff opens Upload, which shows the browser's location. Here a test harness supplies it, and the label says so. The server still validates it."),
  ("k2", "We enter a title, the type Lease, classification Internal, and a sample PDF.")]),
 ("Document saved as Draft", [
  ("k3", "On Upload, the server checks, in order: your token, your role, your location, then the file. It stores the file, computes the hash and writes an audit entry. The document is a Draft.")]),
 ("Supplementary view: the database rows, hash highlighted", [
  ("k4", "In this supplementary view, the real database shows the document and version rows. The highlighted field is the SHA-256 fingerprint: sixty-four characters, and one changed byte changes all of them."),
  ("k5", "The file itself is not in the database. It sits in private storage, RustFS here and Cloudflare R2 in production, under a server-made key that includes the hash.")]),
 ("Document Details, then Version History", [
  ("k6", "The uploader then submits it, and the status becomes Submitted."),
  ("k7", "Version History shows the fingerprint, shortened. The full value is in the database.")]),
],
"s05": [
 ("Upload page, browser location set about a hundred kilometres outside the zone", [
  ("k1", "Now the negative cases. The browser reports a place about a hundred kilometres outside the zone."),
  ("k2", "The server answers geofence denied, and nothing is stored. The server decides, never the browser.")]),
 ("Upload page, location inside the zone but accuracy plus or minus 500 metres", [
  ("k3", "Now the location is inside the zone, but plus or minus 500 metres."),
  ("k4", "The server refuses this too: location low confidence. It's fail-closed: if unsure, it says no. The limit here is three hundred metres.")]),
 ("Supplementary view: the audit log row", [
  ("k5", "The zone denial is written to the audit log, with the claimed position. The low-confidence refusal happens earlier and goes to the application log instead.")]),
 ("Back on the upload page, or a plain slide: the limit", [
  ("k6", "An honest limit: browser location can be faked, for example with developer tools. So geofencing here is policy, not a guarantee of where someone is. The tamper-evidence comes from the blockchain.")]),
],
"s06": [
 ("Document Details as a Legal Officer, on their own seeded document", [
  ("k1", "Next, review and approval, using maker-checker: the person who made a document must not check it."),
  ("k2", "A Legal Officer opens a seeded document they uploaded. No Approve button; someone else must approve."),
  ("k3", "Calling the server directly, from inside the zone, gives maker checker violation. A real response, nothing changed.")]),
 ("Document Details as the Reviewing Officer", [
  ("k4", "Now our lease. A Reviewing Officer, not the uploader, opens it and chooses Review."),
  ("k5", "They pass it, and the status becomes Pending Approval. A reviewer can instead request changes; this app has no rejected state.")]),
 ("Document Details as a different Legal Officer: Approve", [
  ("k6", "A Legal Officer who did not upload it sees the Approve button. Location is checked first."),
  ("k7", "Approval starts anchoring automatically. The backend's own wallet signs, never the user. It's a real transaction on the Sepolia test network, and I trimmed the wait.")]),
 ("Status turns Active", [
  ("k8", "The status becomes Active. It cost a tiny amount of test Ether, worth nothing.")]),
],
"s07": [
 ("Version History: V1 Active and Confirmed, then the Blockchain Anchor Record", [
  ("k1", "Now, what exactly went on the blockchain. Version one is Active and Confirmed. We open View on-chain."),
  ("k2", "Two hashes side by side: on the left, the one in our database; on the right, the one just read live from the Sepolia contract. They are identical: Match.")]),
 ("Anchor Record: network label, contract address, transaction hash", [
  ("k3", "The page also shows the network, the contract address, and the transaction hash, with a Copy button."),
  ("k4", "The contract stores four things per version: the hash, version number, event type and block time. The PDF, filename and names are not on-chain, because a blockchain is public and permanent.")]),
 ("Etherscan transaction page", [
  ("k5", "On the public Etherscan page, the transaction shows Status: Success, and a tiny fee."),
  ("k6", "One service wallet signs every anchor; more on that at the end. And there's no Merkle tree: one hash per file.")]),
],
"s08": [
 ("Repository search as the Public-clearance throwaway user", [
  ("k1", "Now clearance. The throwaway user is Public, and our lease is Internal."),
  ("k2", "The lease isn't listed; the server filters in the database query."),
  ("k3", "Its link shows: That item couldn't be found, or you don't have access.")]),
 ("Supplementary view: two identical 404 answers", [
  ("k4", "The real document and a made-up id give the same answer: four-oh-four, not found. We don't use four-oh-three, forbidden, because that would confirm the document exists.")]),
 ("Administrator opens a seeded Confidential document", [
  ("k5", "The same rule applies to everyone. The Administrator, cleared to Internal, opens a Confidential document and gets a four-oh-four. Administrators get no automatic access to content.")]),
 ("Supplementary view: the audit log, access denied highlighted", [
  ("k6", "A refused attempt on an existing document is audited as access denied. This is access control inside the application, not encryption.")]),
],
"s09": [
 ("Integrity Verification page for version one, as the Legal Officer", [
  ("k1", "Now the core feature: verification. The Legal Officer opens Integrity Verification for version one."),
  ("k2", "The server reads the stored file and recomputes its SHA-256. It compares that with the database hash and the hash read live from the chain."),
  ("k3", "All three match: VERIFIED."),
  ("k4", "A database change alone, or a storage change alone, can't fake VERIFIED. The chain holds the original.")]),
],
"s10": [
 ("Supplementary view: saving the original bytes", [
  ("k1", "Now the attack. First I save a local copy of the original bytes, and check their hash equals the recorded fingerprint.")]),
 ("Supplementary view: the tamper script changes one byte", [
  ("k2", "Now someone with direct storage access changes one byte, bypassing the app. The database and the blockchain still hold the original hash.")]),
 ("Verification page: red MISMATCH banner", [
  ("k3", "We verify again. The result is MISMATCH: the recomputed hash is totally different, while the stored and on-chain hashes agree. That's the avalanche effect."),
  ("k4", "The document is flagged Tampered. The change was made evident, not prevented.")]),
 ("Supplementary view: restoring the original bytes", [
  ("k5", "Now I write the original bytes back, and confirm the hash matches."),
  ("k6", "Verification returns to VERIFIED."),
  ("k7", "But the Tampered flag stays. A later pass doesn't clear it.")]),
 ("Document Details as the Administrator: Clear integrity flag", [
  ("k8", "Only an Administrator can clear it, giving a reason of at least ten characters, written to the audit log."),
  ("k9", "The app re-verifies every anchored version first, and only then clears the flag. The document is clean again.")]),
],
"s11": [
 ("Document Details as the Legal Officer: Request amendment", [
  ("k1", "Now an amendment, which creates version two. Documents are never edited in place; each version is a new, immutable record."),
  ("k2", "The Legal Officer opens the active lease and chooses Request amendment. Location is checked."),
  ("k3", "They give a reason. It moves to Amendment Requested.")]),
 ("Amend upload page as Authorized Staff, then submit", [
  ("k4", "Authorized Staff uploads the amended file, version two. Title, type and classification are copied and can't change."),
  ("k5", "Version two is a Draft, then submitted.")]),
 ("Review, then approve (second transaction)", [
  ("k6", "The three-person rule applies again. Review."),
  ("k7", "Then the Legal Officer who didn't upload it approves. A second real Sepolia transaction, for version two. Again I trim the wait.")]),
 ("Version History: V2 Active and Confirmed, V1 grey Superseded", [
  ("k8", "Version two is Active and Confirmed. Version one carries the grey Superseded badge. The Active badge marks the current version.")]),
 ("Supplementary view: previous-hash field", [
  ("k9", "Hashes are shortened here, so this view shows the proof. Version two's previous-hash equals, character for character, the SHA-256 of version one. That hash link is the connection.")]),
 ("Anchor Record for V2, then Verification of V2 and V1", [
  ("k10", "Version two has its own anchor, hashes side by side, and a Match."),
  ("k11", "Verifying version two gives VERIFIED."),
  ("k12", "Version one still verifies, because its file, hash and anchor are untouched.")]),
],
"s12": [
 ("Document Details: Download button", [
  ("k1", "Now download. The button gives the current version only, now version two. It's geofenced, so location is checked first."),
  ("k2", "The server gives a pre-signed link, valid sixty seconds. The file never passes through the API. I won't show the link.")]),
 ("Supplementary views: downloaded-file hash and the audit row", [
  ("k3", "To prove it's genuine, the harness fetched the file and hashed it. It equals the recorded SHA-256 of version two."),
  ("k4", "The download is audited as ACCESS, as highlighted.")]),
 ("Refused downloads", [
  ("k5", "Now the denials. From outside the zone, Download is refused with geofence denied."),
  ("k6", "A below-clearance viewer inside the zone gets a four-oh-four, so the file is never offered. Zone first, then clearance.")]),
],
"s13": [
 ("Document Details as the Legal Officer: Archive", [
  ("k1", "Finally, archive. The lease is Active, and listed in the repository."),
  ("k2", "The Legal Officer opens it and chooses Archive. No reason field, not geofenced."),
  ("k3", "Status: Archived.")]),
 ("Dashboard and Repository, default view, then the Archived filter", [
  ("k4", "It's gone from the default Dashboard and Repository."),
  ("k5", "It appears under the Archived filter."),
  ("k6", "Archiving keeps every version, anchor and file untouched. There is no restore route; only direct database editing could undo it.")]),
],
"s14": [
 ("Verification page for a seeded draft", [
  ("k1", "There are six verification results. One more, live: a seeded draft that was never approved."),
  ("k2", "The result is NOT ANCHORED. The file is intact, but there's no blockchain record to compare. Not an alarm.")]),
 ("Slide: the six outcomes", [
  ("s1", "Here are all six."),
  ("s2", "VERIFIED: file, record and chain all agree. MISMATCH: the file differs, as we saw."),
  ("s3", "NOT ANCHORED: never approved, nothing on-chain, as we just saw."),
  ("s4", "ANCHOR MISSING: the database says anchored, the chain says no. FILE MISSING: the stored file is gone. CHAIN UNREACHABLE: the chain can't be read, so no verdict."),
  ("s5", "I didn't trigger those last three live.")]),
],
"s15": [
 ("Login page, throwaway account, wrong passwords", [
  ("k1", "Login also has protection. On the throwaway account only, I type wrong passwords."),
  ("k2", "The page counts attempts. Attempt one of five."),
  ("k3", "Attempt two."),
  ("k4", "Attempt three."),
  ("k5", "Attempt four."),
  ("k6", "Attempt five. Sign-in is paused for about a minute."),
  ("k7", "The next try is refused: too many attempts. That slows password guessing.")]),
 ("Supplementary view: login rate limits collection", [
  ("k8", "In MongoDB, login rate limits holds each email's counter and the pause end.")]),
],
"s16": [
 ("Audit Logs page as the Auditor, top of the table", [
  ("k1", "Finally, where everything lives. The Auditor opens Audit Logs, newest first. Every action is a row: who, what, to what, and the result. Rows are only ever added.")]),
 ("Audit Logs filters: action, actor, document", [
  ("k2", "The Action dropdown lists every action in the log. Here, Approve."),
  ("k3", "Actor search finds people by name or email. Here, Legal."),
  ("k4", "The document filter searches titles, only among documents this person may open. Here, a seeded board resolution.")]),
 ("Document Details: View audit trail for our lease", [
  ("k5", "For our lease: View audit trail, one click from its page."),
  ("k6", "This is the lease's whole life, with names instead of ids.")]),
 ("Supplementary views: MongoDB collections and the bucket", [
  ("k7", "Now the MongoDB collections. Users, geofences, documents and versions are the authoritative data. Anchors are derived, since the chain is the real evidence. Verification records and audit logs are history."),
  ("k8", "Ids link them: version to document, anchor to version, storage key to file."),
  ("k9", "MongoDB holds state, fingerprints and audit. The private bucket holds file bytes. The Sepolia contract holds the hash, version, event type and time."),
  ("k10", "One honest gap: the audit log has no hash chain yet, so database writers could alter it.")]),
],
"s17": [
 ("Admin Panel, Reports tab, as the Auditor", [
  ("k1", "The Reports panel covers everything. The Auditor can open it."),
  ("k2", "Anchors confirmed counts successful transactions, including our two."),
  ("k3", "This note reconciles counts. The Auditor can access twenty-two documents, three archived. The Dashboard shows nineteen, since it leaves archived ones out."),
  ("k4", "Mismatches counts our tamper test, and the archived count rose by one: our lease.")]),
],
"s18": [
 ("Summary slide: components", [
  ("a1", "To summarise: React front end, FastAPI back end in Python, and MongoDB for data. RustFS in development and Cloudflare R2 in production store files. web3.py talks to a Solidity smart contract on Sepolia. Docker runs the services, and CI runs the tests.")]),
 ("Slide: honest limits", [
  ("b1", "Honest limits. This is a prototype on a test network. Geofencing is policy, not proof of location. One service wallet signs every anchor. The audit log has no hash chain yet. One SHA-256 per file, no Merkle tree. Verification detects tampering; it does not prevent it.")]),
 ("Slide: future work", [
  ("c1", "Future work, from the project's own tracker: stronger login and secret handling, SEC-01 and SEC-03; deployment hardening, OPS-01; an audit log hash chain, CMP-01; and malware scanning of uploads. Also per-matter access, and richer display names.")]),
 ("Slide: the planned next version", [
  ("d1", "A planned next version reduces trust in the single service wallet. I won't describe it here. Thank you.")]),
],
}
