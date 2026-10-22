"""Scene 16: Audit Logs (opens at the top; action dropdown, actor search, document filter, "View audit trail" from the
document page) and read-only MongoDB / storage supplementary views. Read-only."""
from bson import ObjectId

from common import *
import supp


def collections_lines(st) -> list[str]:
    d = db()
    n = lambda c: d[c].estimated_document_count()
    return [f"database {DEMO_DB}", "",
            f"AUTHORITATIVE   users {n('users')}   geofences {n('geofences')}   documents {n('documents')}   document_versions {n('document_versions')}",
            f"DERIVED         blockchain_anchors {n('blockchain_anchors')}   (the chain is the real evidence)",
            f"HISTORY         verification_records {n('verification_records')}   audit_logs {n('audit_logs')}   (rows are only ever added)",
            f"OPERATIONAL     login_rate_limits {n('login_rate_limits')}   refresh_sessions {n('refresh_sessions')}", "",
            "The audit log has no hash chain yet (CMP-01 is open): someone with database write access could alter it."]


def link_lines(st) -> list[str]:
    d = db()
    nm = supp.names()
    did = ObjectId(st["doc_id"])
    doc = d.documents.find_one({"_id": did})
    out = [f"documents._id                  {did}   ({doc['title']}, owner {nm.get(doc['owner_id'])})",
           f"documents.current_version_id   {doc['current_version_id']}   (-> V2, the ACTIVE version)", ""]
    for v in supp.versions(st["doc_id"]):
        a = d.blockchain_anchors.find_one({"version_id": v["_id"]})
        n = d.verification_records.count_documents({"version_id": v["_id"]})
        out += [f"document_versions._id           {v['_id']}   V{v['version_no']}  document_id -> documents._id  ({v['status']})",
                f"  blockchain_anchors.version_id -> that _id   block {a['block_number']}   tx {a['tx_hash'][:18]}...",
                f"  verification_records.version_id -> that _id   {n} rows",
                f"  storage key                   {v['storage_key']}", ""]
    return out[:-1]


def main(sc, browser):
    st = load_state()
    d = db()
    p = sc.context(browser, "auditor", INSIDE)
    sc.login(p, "auditor")
    p.goto(f"{APP}/audit")
    p.get_by_text("Audit Logs").first.wait_for()
    p.locator("main tbody tr").first.wait_for()
    p.wait_for_timeout(1000)

    with sc.beat(p, "k1", "Audit Logs opens at the top, newest first: who, what, to what, with what result"):
        p.locator("main tbody tr").first.hover()
    with sc.beat(p, "k2", "Action dropdown: every action the log really contains. Here APPROVE"):
        p.locator("main select").first.select_option("APPROVE")
        p.wait_for_timeout(1500)
    with sc.beat(p, "k3", "Actor search: by name or email. Here 'Legal'"):
        p.get_by_placeholder("e.g. Olivia").fill("Legal")
        p.wait_for_timeout(2000)
    with sc.beat(p, "k4", "Document filter: find a document by title (among documents this person may open)"):
        p.get_by_role("button", name="Clear filters").click()
        p.locator("#audit-doc-search").fill("Board Resolution")
        p.get_by_role("list", name="Matching documents").get_by_role("button").first.click()
        p.get_by_text("Showing the history of document").wait_for()
        p.wait_for_timeout(1500)
    p.goto(f"{APP}/documents/{st['doc_id']}")
    p.get_by_role("link", name="View audit trail").wait_for()
    with sc.beat(p, "k5", "From the document page: View audit trail"):
        p.get_by_role("link", name="View audit trail").hover()
        p.get_by_role("link", name="View audit trail").click()
        p.get_by_text("Showing the history of document").wait_for()
        p.locator("main tbody tr").first.wait_for()
    with sc.beat(p, "k6", "The whole life of the lease: names first, ids as secondary text"):
        p.locator("main tbody tr").first.hover()
        p.wait_for_timeout(3000)
        p.mouse.wheel(0, 650)
        p.wait_for_timeout(3500)
        p.mouse.wheel(0, 650)
    with sc.beat(p, "k7", "Supplementary view: the MongoDB collections and what kind of data each holds"):
        show_supp(p, "MongoDB collections: authoritative, derived, history", collections_lines(st))
    with sc.beat(p, "k8", "Supplementary view: how the ids link a document, its versions, anchors and files"):
        show_supp(p, "Id links for the lease (names first; ids are only the keys)", link_lines(st), font=22)
    with sc.beat(p, "k9", "Supplementary view: where the bytes, the state and the hashes live"):
        show_supp(p, "Where each thing lives",
                  supp.bucket_lines(st["doc_id"]) + ["",
                  "MongoDB          state, fingerprints (sha256), anchor records, audit",
                  "private bucket   the file bytes only (RustFS in dev, Cloudflare R2 in production)",
                  "Sepolia contract hash + version + event type + block time per version; no file, no name"],
                  highlight=["v1-", "v2-"])
    p.goto(f"{APP}/audit")
    p.locator("main tbody tr").first.wait_for()
    with sc.beat(p, "k10", "One honest gap: the audit log has no hash chain yet (planned: CMP-01)"):
        p.locator("main tbody tr").first.hover()
    sc.close_role("auditor")


run_scene("scene16_audit_data", "Scene 16 - Audit log, MongoDB and storage", "s16", main)
