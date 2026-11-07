# Speaker script - GeoLegalVault demo v2

Read this while watching `GeoLegalVault_Demo_v2_silent_captions.mp4`. Timestamps are positions on that video (the same as `GeoLegalVault_Demo_v2.mp4`). A sentence's picture appears at its timestamp; start speaking about a quarter of a second after it. Text in [square brackets] is a hint and is **not read aloud**. Every sentence is trimmed to fit at 130 words per minute or less.

---

## Before you record (one page)

### Scenes

| # | Scene | Start - end | Seconds | Words | Avg wpm | Fastest sentence |
|---|---|---|---|---|---|---|
| 0 | Title slide (your scene00 recording) | 0:00 - 0:24 | 24 | - | - | - |
| 1 | The problem and the idea | 0:04 - 1:16 | 72 | 131 | 109 | 128 |
| 2 | Login, roles, clearance and names | 1:16 - 2:25 | 69 | 135 | 117 | 129 |
| 3 | Administrator: zones and users | 2:25 - 3:20 | 55 | 106 | 116 | 130 |
| 4 | Upload version one inside the zone | 3:20 - 4:47 | 87 | 160 | 111 | 126 |
| 5 | Upload refused: outside the zone, and poor accuracy | 4:47 - 5:53 | 66 | 122 | 111 | 129 |
| 6 | Review, maker-checker and approval | 5:53 - 7:15 | 82 | 140 | 102 | 126 |
| 7 | What is anchored on Sepolia | 7:15 - 8:28 | 74 | 129 | 105 | 125 |
| 8 | Clearance: a hidden document is a 404 | 8:28 - 9:33 | 64 | 109 | 102 | 122 |
| 9 | Verify the genuine file: VERIFIED | 9:33 - 10:06 | 33 | 60 | 109 | 125 |
| 10 | Tamper with the stored file, restore it, clear the flag | 10:06 - 11:34 | 88 | 143 | 97 | 127 |
| 11 | Amendment: version two | 11:34 - 13:48 | 134 | 173 | 78 | 129 |
| 12 | Download the current version | 13:48 - 14:43 | 56 | 100 | 108 | 128 |
| 13 | Archive | 14:43 - 15:26 | 43 | 60 | 84 | 121 |
| 14 | The other verification outcomes | 15:26 - 16:22 | 56 | 96 | 103 | 130 |
| 15 | Login protection | 16:22 - 16:59 | 37 | 61 | 99 | 127 |
| 16 | Audit log, MongoDB and storage | 16:59 - 18:34 | 95 | 171 | 108 | 126 |
| 17 | Reports | 18:34 - 19:05 | 31 | 54 | 105 | 129 |
| 18 | Summary and future work | 19:05 - 20:24 | 80 | 142 | 107 | 125 |

**Final video:** it starts with a 24-second title slide, so every main-video timestamp in this script is **+24 s** in `GeoLegalVault_Demo_v2_final.mp4` (exactly 23.98 s when the title clip is 24.48 s; add it to the time shown here). The video is cut at **19:28** of the main video, so what follows is marked **CUT - don't record**: the last part of scene 18's first sentence, and all of its other sentences (scene 18 is almost entirely cut). A 3-second thank-you slide follows.

Total: 20.5 minutes of video, 2092 spoken words. The first 4 seconds and the last 4 seconds are title/end cards with no speech. Avg wpm counts the whole scene including pauses; the real pace while you speak is the 'fastest sentence' figure or lower.

### Key terms to be able to explain

- **Geofence**: a virtual boundary drawn on a map; uploads and approvals are allowed only inside it.
- **SHA-256 hash**: a 64-character fingerprint of a file; change one byte and the whole fingerprint changes.
- **Anchor / anchoring**: writing that fingerprint (never the file) to the public Sepolia test network.
- **Sepolia**: a free Ethereum test network. Test Ether has no real value.
- **Maker-checker**: the person who made a document may not be the one who approves it.
- **Clearance**: Public < Internal < Confidential < Restricted < Top Secret; a document above yours is a 404.
- **404 vs 403**: 404 = not found, 403 = forbidden. 404 is used so a hidden document is not confirmed to exist.
- **Pre-signed link**: a download link that works for 60 seconds; the file never passes through the API.
- **Supplementary view**: a read-only look at the database or storage, labelled as such, not part of the app.
- **Fail-closed**: if the system is not sure about the location, it says no.
- **Service wallet**: the one backend wallet that signs every anchor; users never sign.
- **Merkle tree**: a batching scheme for hashes; not used here. One hash per file.

### Three honest limits - do not skip

- **1. Tamper-evident, not tamper-proof** - 0:45, scene 1: "Anyone can recompute the fingerprint later and check the file. This is tamper-evident: changes are detected, not prevented."
- **2. Geofence is policy, not guaranteed location** - 5:36, scene 5: "An honest limit: browser location can be faked, for example with developer tools. So geofencing here is policy, not a guarantee of where someone is. The tamper-evidence comes from the blockchain."
- **3. The audit log has no hash chain yet** - 18:24, scene 16: "One honest gap: the audit log has no hash chain yet, so database writers could alter it."
- The closing summary of limits (scene 18, 19:29) is after the 19:28 cut, so in the **final** video these three, said earlier, are the only places the limits are stated. In the uncut video it repeats them.
- Say: prototype, Sepolia test network, tamper-evident, policy-level geofencing. Never say: tamper-proof, unhackable, guaranteed location. The app has no rejected state: say "changes requested".

---

## Scene 0 - Title slide

**Final video only:** 0:00 - 0:24 (24 seconds; your recording `scene00.wav` is 24.48 s). The slide shows the project, the three team members, the course and the faculty. Suggested wording (about 40 words, easy at 130 wpm); skip this if your scene00.wav is already recorded:

> **ON SCREEN:** Title slide: GeoLegalVault, team members, course details

- `0:00` Good day. This is GeoLegalVault, a course project for Blockchain Technologies, C-S-E four-oh-seven-eight, at Vellore Institute of Technology. We are Ekanath D V, S. Mohamed Faizal and Rohan Julius Preetan, with our faculty, Doctor Jayanthi R. This is a live demonstration.

---

## Scene 1 - The problem and the idea

**Silent video:** 0:04 - 1:16 (72 seconds available) | 131 words | about 109 words per minute over the scene, fastest sentence 128

> **ON SCREEN:** Title card, then Slide 1: the problem

- `0:13` Second, any login works from anywhere.

> **ON SCREEN:** Slide 2: what GeoLegalVault does

- `1:05` Everything is the real system on a test network. Where the screen can't show something, I label it a supplementary view.

---

## Scene 2 - Login, roles, clearance and names

**Silent video:** 1:16 - 2:25 (69 seconds available) | 135 words | about 117 words per minute over the scene, fastest sentence 129

> **ON SCREEN:** Login page, then the Dashboard as Authorized Staff

- `1:39` These counts come from the server and differ per person. The vault holds twenty-one demo documents, two archived, which these counts leave out.

> **ON SCREEN:** A second browser session: Legal Officer, then Administrator

- `2:12` Everyone also has a clearance level: Public, Internal, Confidential, Restricted or Top Secret. The menu is a convenience; the server checks role and clearance on every request.

---

## Scene 3 - Administrator: zones and users

**Silent video:** 2:25 - 3:20 (55 seconds available) | 106 words | about 116 words per minute over the scene, fastest sentence 130

> **ON SCREEN:** Admin Panel, Geofences tab

- `2:31` A zone is a polygon of longitude and latitude pairs, always in that order. The form previews the centre, as a visual aid only. Our demo zone, HQ Campus [H-Q], is the small box below, near latitude eleven point six seven, longitude seventy-eight point one five. The server tests every request against it.

> **ON SCREEN:** Admin Panel, Users tab: creating the throwaway user

- `3:13` The new account appears. We use it later, for hidden documents and login limits.

---

## Scene 4 - Upload version one inside the zone

**Silent video:** 3:20 - 4:47 (87 seconds available) | 160 words | about 111 words per minute over the scene, fastest sentence 126

> **ON SCREEN:** Upload page as Authorized Staff

- `3:39` We enter a title, the type Lease, classification Internal, and a sample PDF.

> **ON SCREEN:** Document saved as Draft

- `3:46` On Upload, the server checks, in order: your token, your role, your location, then the file. It stores the file, computes the hash and writes an audit entry. The document is a Draft.

> **ON SCREEN:** Supplementary view: the database rows, hash highlighted

- `4:17` The file itself is not in the database. It sits in private storage, RustFS [Rust-F-S] here and Cloudflare R2 [say: Cloudflare R-two] in production, under a server-made key that includes the hash.
  - **[PAUSE 3s]** the video holds here, no narration

> **ON SCREEN:** Document Details, then Version History

- `4:39` Version History shows the fingerprint, shortened. The full value is in the database.

---

## Scene 5 - Upload refused: outside the zone, and poor accuracy

**Silent video:** 4:47 - 5:53 (66 seconds available) | 122 words | about 111 words per minute over the scene, fastest sentence 129

> **ON SCREEN:** Upload page, browser location set about a hundred kilometres outside the zone

- `4:55` The server answers geofence [JEE-oh-fence] denied, and nothing is stored. The server decides, never the browser.

> **ON SCREEN:** Upload page, location inside the zone but accuracy plus or minus 500 metres

- `5:10` The server refuses this too: location low confidence [on screen: LOCATION_LOW_CONFIDENCE]. It's fail-closed: if unsure, it says no. The limit here is three hundred metres.

> **ON SCREEN:** Supplementary view: the audit log row

- `5:23` The zone denial is written to the audit log, with the claimed position. The low-confidence refusal happens earlier and goes to the application log instead.

> **ON SCREEN:** Back on the upload page, or a plain slide: the limit

- `5:36` An honest limit: browser location can be faked, for example with developer tools. So geofencing here is policy, not a guarantee of where someone is. The tamper-evidence comes from the blockchain. **★ MUST SAY (geofencing is policy, not a guarantee of location)**

---

## Scene 6 - Review, maker-checker and approval

**Silent video:** 5:53 - 7:15 (82 seconds available) | 140 words | about 102 words per minute over the scene, fastest sentence 126

> **ON SCREEN:** Document Details as a Legal Officer, on their own seeded document

- `6:10` Calling the server directly, from inside the zone, gives maker checker violation [on screen: MAKER_CHECKER_VIOLATION]. A real response, nothing changed.
  - **[PAUSE 3s]** the video holds here, no narration

> **ON SCREEN:** Document Details as the Reviewing Officer

- `6:30` They pass it, and the status becomes Pending Approval. A reviewer can instead request changes; this app has no rejected state.

> **ON SCREEN:** Document Details as a different Legal Officer: Approve

- `6:50` Approval starts anchoring automatically. The backend's own wallet signs, never the user. It's a real transaction on the Sepolia [seh-POH-lee-uh] test network, and I trimmed the wait.
  - **[PAUSE 4s]** the video holds here, no narration

> **ON SCREEN:** Status turns Active

- `7:08` The status becomes Active. It cost a tiny amount of test Ether [EE-ther], worth nothing.

---

## Scene 7 - What is anchored on Sepolia

**Silent video:** 7:15 - 8:28 (74 seconds available) | 129 words | about 105 words per minute over the scene, fastest sentence 125

> **ON SCREEN:** Version History: V1 Active and Confirmed, then the Blockchain Anchor Record

- `7:24` Two hashes side by side: on the left, the one in our database; on the right, the one just read live from the Sepolia contract. They are identical: Match.

> **ON SCREEN:** Anchor Record: network label, contract address, transaction hash

- `7:49` The contract stores four things per version: the hash, version number, event type and block time. The PDF, filename and names are not on-chain, because a blockchain is public and permanent.
  - **[PAUSE 5s]** the video holds here, no narration

> **ON SCREEN:** Etherscan transaction page

- `8:18` One service wallet signs every anchor; more on that at the end. And there's no Merkle [MUR-kul] tree: one hash per file.

---

## Scene 8 - Clearance: a hidden document is a 404

**Silent video:** 8:28 - 9:33 (64 seconds available) | 109 words | about 102 words per minute over the scene, fastest sentence 122

> **ON SCREEN:** Repository search as the Public-clearance throwaway user

- `8:42` Its link shows: That item couldn't be found, or you don't have access.

> **ON SCREEN:** Supplementary view: two identical 404 answers

- `8:49` The real document and a made-up id give the same answer: four-oh-four [404], not found. We don't use four-oh-three [403], forbidden, because that would confirm the document exists.
  - **[PAUSE 3s]** the video holds here, no narration

> **ON SCREEN:** Administrator opens a seeded Confidential document

- `9:05` The same rule applies to everyone. The Administrator, cleared to Internal, opens a Confidential document and gets a four-oh-four. Administrators get no automatic access to content.
  - **[PAUSE 3s]** the video holds here, no narration

> **ON SCREEN:** Supplementary view: the audit log, access denied highlighted

- `9:21` A refused attempt on an existing document is audited as access denied [on screen: ACCESS_DENIED]. This is access control inside the application, not encryption.

---

## Scene 9 - Verify the genuine file: VERIFIED

**Silent video:** 9:33 - 10:06 (33 seconds available) | 60 words | about 109 words per minute over the scene, fastest sentence 125

> **ON SCREEN:** Integrity Verification page for version one, as the Legal Officer

- `9:57` A database change alone, or a storage change alone, can't fake VERIFIED. The chain holds the original.

---

## Scene 10 - Tamper with the stored file, restore it, clear the flag

**Silent video:** 10:06 - 11:34 (88 seconds available) | 143 words | about 97 words per minute over the scene, fastest sentence 127

> **ON SCREEN:** Supplementary view: saving the original bytes

- `10:06` Now the attack. First I save a local copy of the original bytes, and check their hash equals the recorded fingerprint.

> **ON SCREEN:** Supplementary view: the tamper script changes one byte

- `10:18` Now someone with direct storage access changes one byte, bypassing the app. The database and the blockchain still hold the original hash.
  - **[PAUSE 4s]** the video holds here, no narration

> **ON SCREEN:** Verification page: red MISMATCH banner

- `10:50` The document is flagged Tampered. The change was made evident, not prevented.

> **ON SCREEN:** Supplementary view: restoring the original bytes

- `11:09` But the Tampered flag stays. A later pass doesn't clear it.

> **ON SCREEN:** Document Details as the Administrator: Clear integrity flag

- `11:25` The app re-verifies every anchored version first, and only then clears the flag. The document is clean again.

---

## Scene 11 - Amendment: version two

**Silent video:** 11:34 - 13:48 (134 seconds available) | 173 words | about 78 words per minute over the scene, fastest sentence 129

> **ON SCREEN:** Document Details as the Legal Officer: Request amendment

- `12:18` They give a reason. It moves to Amendment Requested.

> **ON SCREEN:** Amend upload page as Authorized Staff, then submit

- `12:33` Version two is a Draft, then submitted.

> **ON SCREEN:** Review, then approve (second transaction)

- `12:43` Then the Legal Officer who didn't upload it approves. A second real Sepolia transaction, for version two. Again I trim the wait.

> **ON SCREEN:** Version History: V2 Active and Confirmed, V1 grey Superseded

- `12:56` Version two is Active and Confirmed. Version one carries the grey Superseded [soo-per-SEE-did] badge. The Active badge marks the current version.
  - **[PAUSE 4s]** the video holds here, no narration

> **ON SCREEN:** Supplementary view: previous-hash field

- `13:11` Hashes are shortened here, so this view shows the proof. Version two's previous-hash equals, character for character, the SHA-256 [say: S-H-A two-fifty-six] of version one. That hash link is the connection.
  - **[PAUSE 3s]** the video holds here, no narration

> **ON SCREEN:** Anchor Record for V2, then Verification of V2 and V1

- `13:38` Version one still verifies, because its file, hash and anchor are untouched.
  - **[PAUSE 3s]** the video holds here, no narration

---

## Scene 12 - Download the current version

**Silent video:** 13:48 - 14:43 (56 seconds available) | 100 words | about 108 words per minute over the scene, fastest sentence 128

> **ON SCREEN:** Document Details: Download button

- `13:58` The server gives a pre-signed [pre-SIGNED] link, valid sixty seconds. The file never passes through the API. I won't show the link.

> **ON SCREEN:** Supplementary views: downloaded-file hash and the audit row

- `14:19` The download is audited as ACCESS, as highlighted.

> **ON SCREEN:** Refused downloads

- `14:32` A below-clearance viewer inside the zone gets a four-oh-four, so the file is never offered. Zone first, then clearance.

---

## Scene 13 - Archive

**Silent video:** 14:43 - 15:26 (43 seconds available) | 60 words | about 84 words per minute over the scene, fastest sentence 121

> **ON SCREEN:** Document Details as the Legal Officer: Archive

- `14:58` Status: Archived.

> **ON SCREEN:** Dashboard and Repository, default view, then the Archived filter

- `15:12` Archiving keeps every version, anchor and file untouched. There is no restore route; only direct database editing could undo it.
  - **[PAUSE 5s]** the video holds here, no narration

---

## Scene 14 - The other verification outcomes

**Silent video:** 15:26 - 16:22 (56 seconds available) | 96 words | about 103 words per minute over the scene, fastest sentence 130

> **ON SCREEN:** Verification page for a seeded draft

- `15:34` The result is NOT ANCHORED [on screen: NOT_ANCHORED]. The file is intact, but there's no blockchain record to compare. Not an alarm.

> **ON SCREEN:** Slide: the six outcomes

- `16:16` I didn't trigger those last three live.

---

## Scene 15 - Login protection

**Silent video:** 16:22 - 16:59 (37 seconds available) | 61 words | about 99 words per minute over the scene, fastest sentence 127

> **ON SCREEN:** Login page, throwaway account, wrong passwords

- `16:45` The next try is refused: too many attempts. That slows password guessing.

> **ON SCREEN:** Supplementary view: login rate limits collection

- `16:52` In MongoDB [MON-go-D-B], login rate limits [on screen: login_rate_limits] holds each email's counter and the pause end.

---

## Scene 16 - Audit log, MongoDB and storage

**Silent video:** 16:59 - 18:34 (95 seconds available) | 171 words | about 108 words per minute over the scene, fastest sentence 126

> **ON SCREEN:** Audit Logs page as the Auditor, top of the table

- `16:59` Finally, where everything lives. The Auditor opens Audit Logs, newest first. Every action is a row: who, what, to what, and the result. Rows are only ever added.

> **ON SCREEN:** Audit Logs filters: action, actor, document

- `17:25` The document filter searches titles, only among documents this person may open. Here, a seeded board resolution.

> **ON SCREEN:** Document Details: View audit trail for our lease

- `17:41` This is the lease's whole life, with names instead of ids.

> **ON SCREEN:** Supplementary views: MongoDB collections and the bucket

- `18:24` One honest gap: the audit log has no hash chain yet, so database writers could alter it. **★ MUST SAY (the audit log has no hash chain yet)**

---

## Scene 17 - Reports

**Silent video:** 18:34 - 19:05 (31 seconds available) | 54 words | about 105 words per minute over the scene, fastest sentence 129

> **ON SCREEN:** Admin Panel, Reports tab, as the Auditor

- `18:57` Mismatches counts our tamper test, and the archived count rose by one: our lease.

---

## Scene 18 - Summary and future work

**Silent video:** 19:05 - 20:24 (80 seconds available) | 142 words | about 107 words per minute over the scene, fastest sentence 125

> **ON SCREEN:** Summary slide: components

- `19:05` To summarise: React front end, FastAPI [Fast-A-P-I] back end in Python, and MongoDB for data. RustFS in development and Cloudflare R2 in production store files. web3.py [web-three dot P-Y] talks to a Solidity [sol-ID-ih-tee] smart contract on Sepolia. Docker runs the services, and CI runs the tests. **ENDS AT 19:28 - the final video cuts here; the voice fades out. Say it at your normal pace, the last words are cut**
  - **[PAUSE 4s]** the video holds here, no narration

> **ON SCREEN:** Slide: honest limits

- `19:29` Honest limits. This is a prototype on a test network. Geofencing is policy, not proof of location. One service wallet signs every anchor. The audit log has no hash chain yet. One SHA-256 per file, no Merkle tree. Verification detects tampering; it does not prevent it. **CUT - don't record**

> **ON SCREEN:** Slide: future work

- `19:52` Future work, from the project's own tracker: stronger login and secret handling, SEC-01 [S-E-C zero-one] and SEC-03 [S-E-C zero-three]; deployment hardening, OPS-01 [O-P-S zero-one]; an audit log hash chain, CMP-01 [C-M-P zero-one]; and malware scanning of uploads. Also per-matter access, and richer display names. **CUT - don't record**
  - **[PAUSE 6s]** the video holds here, no narration

> **ON SCREEN:** Slide: the planned next version

- `20:15` A planned next version reduces trust in the single service wallet. I won't describe it here. Thank you. **CUT - don't record**

---
