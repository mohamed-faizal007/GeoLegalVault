# Research Methodology — GeoLegalVault

## Framing

GeoLegalVault is best framed as an **experience/architecture/evaluation** contribution,
not a novel-algorithm paper (Plan Part 29). Hash-anchoring documents on-chain is a
well-established pattern (notary/timestamping services); RBAC document management and
mobility-app geofencing are both standard. The honest contribution is the *specific
integration*: geospatial authorization as a first-class gate on document-lifecycle
operations, combined with per-version on-chain anchoring and immutable version lineage, in
one working system with an honestly-stated threat model (Plan Part 27).

## Research question

*What are the practical benefits, costs, and security limits of combining geospatial
authorization with per-version blockchain anchoring in a document-lifecycle system, and
where does browser-based geofencing fail as a security control?*

## Method

1. Build the system (this repo) — implemented in 12 phases: identity/RBAC, geofence
   enforcement, storage/hashing/versioning, contract + anchoring, lifecycle workflow, the
   3-way verification loop, audit logging, frontend, admin/reporting, testing/CI,
   deployment.
2. Run controlled experiments against it:
   - **Tamper detection:** anchor a version, deliberately alter one byte in its stored
     blob, run Verify — expect MISMATCH every time (`tests/integration/test_verify.py`
     exercises this as an automated test, not just a manual demo step).
   - **Database-level tamper:** additionally alter the *stored hash in MongoDB* to match
     the tampered file, run Verify again — expect it to still MISMATCH against the
     immutable on-chain hash. This isolates exactly what the blockchain anchor buys over a
     database-only signed hash: an admin/insider who can edit the database cannot also
     edit the chain.
   - **Geofence in/out:** attempt the same operation from a point inside vs. outside an
     assigned zone — expect allow vs. 403, with both outcomes audited.
   - **Spoofing attempt:** override the browser's reported location (DevTools sensor
     override) to a point inside a zone while physically elsewhere — expect the operation
     to **succeed**, because the server has no way to distinguish a spoofed coordinate from
     a real one. This is the experiment whose result the report should state plainly, not
     minimize.
3. Measure latencies (upload, verify, anchor confirmation) and qualitatively analyze the
   threat model (`THREAT_MODEL.md`).

## Metrics

| Metric | How measured | Expected/observed |
|---|---|---|
| Integrity-detection accuracy | Fraction of controlled byte-changes that produce MISMATCH | 100% — SHA-256's avalanche effect means any change is detected; not probabilistic |
| Verify latency (fetch + hash + on-chain read) | Client/server timers | Sub-3s target (Plan Part 22); dominated by the on-chain read (RPC round trip), not the hashing itself |
| Anchor latency | Tx submission → confirmation | Seconds to ~2 min on Sepolia, intentionally async and never blocking the UI |
| Anchor gas cost | Sepolia is free-faucet testnet ETH — cost is ₹0, but relative gas usage is still comparable: one `SSTORE` + one event per anchor, no loops, no per-byte cost (only the hash + small metadata go on-chain) |
| Geofence decision correctness | Point-in-polygon test cases: inside / outside / on-edge / low-accuracy / stale | Deterministic per MongoDB's `$geoIntersects`; edge-of-polygon behavior is whatever the geometry engine's boundary convention is — document it, don't assume |
| Spoofing-detection rate | Fraction of spoofed-location attempts the *system* catches | **~0%, expected and reported honestly** — the system does not attempt to detect spoofing; this null result is itself informative, not a failure of the experiment |

## Baselines

- **DB-only integrity** (a signed hash stored only in MongoDB, no chain) vs. **chain-
  anchored**: the DB-tamper experiment above is exactly this comparison — a DB-only scheme
  is defeated by an actor who can also edit the DB; the chain-anchored scheme is not
  (within the threat model's stated bounds — a compromised service-wallet key is a
  separate, differently-mitigated threat, see `THREAT_MODEL.md` #13).
- **Access control with vs. without geofencing**: the same permission check, once gated
  additionally on location and once not — quantifies what the geofence *adds* (a
  legitimate, credentialed user can still be blocked by location) and what it does *not*
  add (protection against a spoofed location from a credentialed user).

## Expected / actual results

Cryptographic tamper-evidence works reliably and unconditionally — every controlled
tamper test in `tests/integration/test_verify.py` produces MISMATCH, with no false
negatives across the DB-tamper variant either. Geofencing adds real policy value (it does
stop a credentialed user from acting outside an authorized zone when they aren't
deliberately spoofing) but is bypassable by anyone willing to spoof their browser's
reported location — this is the honest negative result the plan calls a real contribution
in its own right (Plan Part 29), not a shortcoming to bury in an appendix.

## Limitations

- Browser GPS spoofability (the central limitation — stated in the threat model, the demo
  script's closing slide, and here, deliberately repeated rather than mentioned once).
- Sepolia testnet reliability/impermanence; RPC free-tier rate limits.
- Custodial (single service-wallet) signing, not per-user cryptographic attestation.
- Small scale: a synthetic dataset (~30–50 documents, Plan Part 21), not a production
  workload; no sustained load testing.
- No malware scanning (MIME/magic-byte validation only) and no periodic audit-log
  hash-chaining — both named, deferred hardening items, not oversights (see
  `THREAT_MODEL.md`).

## Positioning relative to a companion project (TARP)

If a related project on hierarchical hashing / Merkle trees / NLP-based tamper
*localization* exists in the same programme, the boundary is: this project proves
*whole-document and whole-version* integrity and enforces *where* operations happen; a
Merkle/NLP-based project would additionally localize and semantically characterize *where
inside* a document a change occurred. This project intentionally does not implement
Merkle trees or NLP (Guardrail #8) to keep that boundary clean.
