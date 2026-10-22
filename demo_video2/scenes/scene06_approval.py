"""Scene 6: maker-checker, review, and approval with ONE real Sepolia testnet transaction (V1).

NOT re-runnable once it has approved (state flag). If the anchor does not confirm inside the request window the scene
stops and reports; it never starts the worker and never retries. The self-approval demo uses a SEEDED PENDING_APPROVAL
document uploaded by the Legal Officer; the script first checks that the uploader really is the caller, so the server's
maker-checker rule (which runs before anything touches the chain) must refuse it, and afterwards that nothing changed.
"""
import json
import time

from bson import ObjectId

from common import *
import supp


def status_text(p) -> str:
    return p.locator("main").inner_text()


def main(sc, browser):
    st = load_state()
    if st.get("v1_approved_at"):
        raise SystemExit("V1 was already approved once; refusing to send a second transaction.")
    d = db()
    legal_user = d.users.find_one({"email": EMAILS["legal"]})
    seeded = d.documents.find_one({"title": "Shareholder Agreement Amendment - Series B Terms"})
    sv = d.document_versions.find_one({"document_id": seeded["_id"]}, sort=[("version_no", -1)])
    assert seeded["status"] == "PENDING_APPROVAL" and sv["uploaded_by"] == legal_user["_id"], "seeded doc is not as expected"
    seeded_id = str(seeded["_id"])

    legal = sc.context(browser, "legal", INSIDE)
    sc.login(legal, "legal")
    legal.goto(f"{APP}/documents/{seeded_id}")
    legal.get_by_text("someone else must").first.wait_for()

    with sc.beat(legal, "k1", "Maker-checker: the person who made a document must not be the one who checks it"):
        legal.locator("main h1").first.hover()
    with sc.beat(legal, "k2", "Seeded document uploaded by this Legal Officer: no Approve button; someone else must approve"):
        legal.locator("main").get_by_text("someone else must").first.hover()
    tok = token_for(EMAILS["legal"], demo_password())
    s2, resp = api("POST", f"/documents/{seeded_id}/approve", token=tok, headers=geo_headers(INSIDE))
    assert s2 == 403, f"expected 403, got {s2}"
    assert d.documents.find_one({"_id": seeded["_id"]})["status"] == "PENDING_APPROVAL", "seeded doc changed!"
    with sc.beat(legal, "k3", "Supplementary view: a real API call where the uploader tries to approve their own document"):
        show_supp(legal, "POST /api/v1/documents/<seeded document id>/approve   as the uploader, from inside the zone",
                  [f"HTTP {s2}", *json.dumps(resp, indent=2).splitlines(), "",
                   "Order of checks: token, role, location, then the maker-checker rule.",
                   "The UI offers no such button; this call was sent directly to the API.",
                   "Result: nothing changed. The document is still PENDING_APPROVAL and nothing was anchored."],
                  highlight=["MAKER_CHECKER_VIOLATION", "HTTP 403"])

    rev = sc.context(browser, "reviewer", INSIDE)
    sc.login(rev, "reviewer")
    rev.goto(f"{APP}/documents/{st['doc_id']}")
    rev.get_by_role("button", name="Review", exact=True).wait_for()
    with sc.beat(rev, "k4", "Reviewing Officer (a different person) opens the lease: status SUBMITTED, a Review button"):
        rev.get_by_role("button", name="Review", exact=True).click()
        rev.wait_for_timeout(1000)
    with sc.beat(rev, "k5", "Review passed: status PENDING_APPROVAL. There is no rejected state; changes requested loops back"):
        rev.fill("textarea", "Content checked. No personal data. Approved for the next step.")
        rev.get_by_role("button", name="Approve review").click()
        rev.get_by_text("PENDING APPROVAL", exact=True).first.wait_for()
    sc.close_role("reviewer")

    legal.goto(f"{APP}/documents/{st['doc_id']}")
    legal.get_by_role("button", name="Approve", exact=True).wait_for()
    bal_before = wallet_balance()
    save_state(bal_before_v1=bal_before)
    with sc.beat(legal, "k6", "Legal Officer who did not upload it: the Approve button is there; location is checked first", geo=True):
        legal.get_by_role("button", name="Approve", exact=True).hover()
    with sc.beat(legal, "k7", "Approve: anchoring starts automatically; the backend wallet signs on Sepolia TESTNET (wait trimmed)", geo=True):
        legal.get_by_role("button", name="Approve", exact=True).click()
        save_state(v1_approved_at=time.time())
        sc.hold_audio(legal)
        t_click = time.time()
        with sc.trimmed():
            while True:
                txt = status_text(legal)
                if legal.locator("main").get_by_text("ACTIVE", exact=True).count():
                    break
                if "Working" not in txt and legal.locator("main").get_by_text("APPROVED", exact=True).count() and time.time() - t_click > 25:
                    save_state(v1_anchor_stuck=True)
                    raise SystemExit("STOP: V1 is APPROVED but the anchor did not confirm in the request window. "
                                     "Not starting the worker and not retrying; report to the user.")
                if time.time() - t_click > 170:
                    save_state(v1_anchor_stuck=True)
                    raise SystemExit("STOP: no ACTIVE status within 170 s; report to the user.")
                legal.wait_for_timeout(1000)
    a = d.blockchain_anchors.find_one({"document_id": ObjectId(st["doc_id"])})
    save_state(tx_v1=a["tx_hash"], block_v1=a["block_number"], bal_after_v1=wallet_balance())
    print("V1 anchor status:", a["status"], "block", a["block_number"])
    with sc.beat(legal, "k8", "Status ACTIVE: the anchor was confirmed on the Sepolia testnet (test Ether has no real value)"):
        legal.locator("main").get_by_text("ACTIVE", exact=True).first.hover()
    sc.close_role("legal")


run_scene("scene06_approval", "Scene 6 - Review, maker-checker, approval", "s06", main)
