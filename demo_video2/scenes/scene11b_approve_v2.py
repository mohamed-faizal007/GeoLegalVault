"""Scene 11, part 2: approve V2 -> the second real Sepolia testnet transaction, then Version History, the hash link, the
V2 anchor page and verification of V2 and V1.

Why this is a separate script: the first run of part 1 also tried to approve, but the Legal Officer's browser location
had been set minutes earlier, so the server refused it with LOCATION_STALE (a reading older than the freshness limit)
BEFORE approving anything (no APPROVE audit row, no anchor, no gas spent). The harness now refreshes the location right
before every geofenced beat. This script checks that V2 really is still PENDING_APPROVAL with no anchor, so it cannot
send a second transaction for the same version, and it stops (no worker, no retry loop) if the anchor does not confirm.
"""
import time

from bson import ObjectId

from common import *
from flows import run_verify, wait_active
import supp


def main(sc, browser):
    st = load_state()
    d = db()
    doc = d.documents.find_one({"_id": ObjectId(st["doc_id"])})
    v1, v2 = supp.versions(st["doc_id"])
    assert doc["status"] == "PENDING_APPROVAL" and v2["status"] == "PENDING_APPROVAL" and not v2.get("anchored"), \
        "V2 is not in the expected PENDING_APPROVAL state; refusing to approve"
    assert d.blockchain_anchors.count_documents({"version_id": v2["_id"]}) == 0, "V2 already has an anchor row"
    assert d.audit_logs.count_documents({"action": "APPROVE", "target_id": doc["_id"]}) == 1, "an APPROVE for V2 was recorded"
    save_state(v2_approved_at=None, v2_anchor_stuck=False, v2_first_attempt="LOCATION_STALE (refused before approving; no tx)")
    doc_url = f"{APP}/documents/{st['doc_id']}"

    legal = sc.context(browser, "legal", INSIDE)
    sc.login(legal, "legal")
    legal.goto(doc_url)
    legal.get_by_role("button", name="Approve", exact=True).wait_for()
    save_state(bal_before_v2=wallet_balance())
    with sc.beat(legal, "k7", "Legal Officer (not the V2 uploader) approves: second real Sepolia TESTNET transaction (wait trimmed)", geo=True):
        legal.get_by_role("button", name="Approve", exact=True).click()
        t_click = time.time()
        save_state(v2_approved_at=t_click)
        sc.hold_audio(legal)
        wait_active(sc, legal, save_state, "v2_anchor_stuck", t_click, "V2")
    a2 = d.blockchain_anchors.find_one({"version_id": v2["_id"]})
    save_state(tx_v2=a2["tx_hash"], block_v2=a2["block_number"], bal_after_v2=wallet_balance())
    print("V2 anchor status:", a2["status"], "block", a2["block_number"])

    with sc.beat(legal, "k8", "Version History: V2 ACTIVE + CONFIRMED; V1 now has the grey SUPERSEDED badge; no 'current' label"):
        legal.goto(f"{APP}/documents/{st['doc_id']}/versions")
        legal.locator("main").get_by_text("SUPERSEDED", exact=True).first.wait_for()
        legal.locator("main").get_by_text("SUPERSEDED", exact=True).first.hover()
    v1, v2 = supp.versions(st["doc_id"])
    with sc.beat(legal, "k9", "Supplementary view: V2's previous-hash equals V1's SHA-256 (there is no parent_version_id field)"):
        show_supp(legal, "document_versions: the parent link is the hash itself",
                  [f"V1  version_no = 1   sha256              {v1['sha256']}",
                   f"V2  version_no = 2   prev_version_hash    {v2['prev_version_hash']}", "",
                   "prev_version_hash (V2) == sha256 (V1)  ->  TRUE, character for character", "",
                   "fields on a version row:  " + ", ".join(sorted(k for k in v2.keys() if k != "_id")),
                   "(no parent_version_id field exists)"],
                  highlight=[v1["sha256"], "TRUE", "no parent_version_id field exists"], font=26)
    with sc.beat(legal, "k10", "V2 anchor record: recorded hash and live on-chain hash side by side: Match"):
        legal.goto(f"{APP}/versions/{v2['_id']}/blockchain")
        legal.wait_for_selector("[data-testid=hash-comparison]")
        sc.zoom(legal, 1.05)
        legal.locator("[data-testid=hash-comparison]").hover()
    with sc.beat(legal, "k11", "Verify V2: VERIFIED"):
        legal.goto(f"{APP}/verify/{v2['_id']}")
        legal.get_by_role("button", name="Run verification").wait_for()
        run_verify(legal, "VERIFIED")
    with sc.beat(legal, "k12", "V1 still verifies: VERIFIED. The Verification page never mentions 'superseded'"):
        legal.goto(f"{APP}/verify/{v1['_id']}")
        legal.get_by_role("button", name="Run verification").wait_for()
        run_verify(legal, "VERIFIED")
        legal.locator("main").get_by_text("Verification history").first.hover()
    sc.close_role("legal")
    save_state(v2_done=True)


run_scene("scene11b_approve_v2", "Scene 11 - Amendment: version two", "s11", main)
