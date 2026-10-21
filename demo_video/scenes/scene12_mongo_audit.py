"""Scene 12: audit log (UI, as Auditor) and a read-only MongoDB / storage deep dive (supplementary views)."""
from bson import ObjectId

from common import *
import supp


def collections_view(st) -> str:
    d = db()
    did = ObjectId(st["doc_id"])
    ver = d.document_versions.find_one({"document_id": did})
    counts = {c: d[c].estimated_document_count() for c in
              ("users", "geofences", "documents", "document_versions", "blockchain_anchors",
               "verification_records", "audit_logs")}
    anchor = d.blockchain_anchors.find_one({"version_id": ver["_id"]}, {"tx_hash": 1, "block_number": 1, "status": 1})
    return ("Collections (document counts):\n" + supp._j(counts) +
            "\n\nHow one document is linked (ids only):\n"
            f"  documents._id                 = {did}\n"
            f"  documents.current_version_id  = {d.documents.find_one({'_id': did})['current_version_id']}\n"
            f"  document_versions._id         = {ver['_id']}   (document_id -> documents._id)\n"
            f"  blockchain_anchors.version_id = {ver['_id']}   status={anchor['status']} block={anchor['block_number']}\n"
            f"  verification_records.version_id -> {ver['_id']}   rows: {d.verification_records.count_documents({'version_id': ver['_id']})}\n"
            f"  storage key                   = {ver['storage_key']}\n"
            "\nAuthoritative: users, geofences, documents, document_versions.   Derived: blockchain_anchors (the chain is the evidence).\n"
            "Audit / history: audit_logs, verification_records.   The audit log has no hash chain yet (CMP-01 is open).")


def main(sc, browser):
    st = load_state()
    p = sc.context(browser, "auditor", INSIDE)
    sc.say(p, "Auditor signs in and opens Audit Logs")
    sc.login(p, "auditor")
    p.goto(f"{APP}/audit")
    p.wait_for_timeout(5000)
    sc.say(p, "Audit Logs: who did what, to what, with what result. Rows are only ever added")
    p.mouse.wheel(0, 500)
    p.wait_for_timeout(9000)

    sc.say(p, "Supplementary view: audit_logs rows written by this demo document")
    show_text(p, "audit_logs for the lease document and its version", supp.audit_view(st["doc_id"], limit=20))
    p.wait_for_timeout(16000)
    sc.say(p, "Supplementary view: collections and how ids link them")
    show_text(p, "MongoDB database geolegalvault", collections_view(st))
    p.wait_for_timeout(18000)
    sc.say(p, "Supplementary view: the private bucket and the blockchain record")
    show_text(p, "Where each thing lives",
              supp.bucket_listing(st["doc_id"]) + "\n\n" + supp.anchor_view(st["doc_id"]) +
              "\n\nMongoDB: state, fingerprints, anchor records, audit.   RustFS/R2: the file bytes.   Sepolia contract: hash + version + event type + time only.")
    p.wait_for_timeout(18000)


run_scene("scene12_mongo_audit", "Scene 12 - Audit log and data", main)
