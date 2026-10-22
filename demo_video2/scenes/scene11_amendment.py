"""Scene 11, part 1: amendment V2 up to the review. Request amendment (Legal Officer, geofenced) -> upload V2 (Authorized
Staff, geofenced) -> submit -> review (Reviewing Officer). Part 2 (scene11b_approve_v2.py) approves and anchors (the
second Sepolia transaction). Creates a version: not re-runnable.
"""
from common import *
import supp

PDF2 = VID / "samples" / "DEMO_Lease_v2.pdf"
REASON = "Rent revised to INR 27,500 per month, as agreed."


def main(sc, browser):
    st = load_state()
    if db().document_versions.count_documents({"document_id": __import__("bson").ObjectId(st["doc_id"])}) > 1:
        raise SystemExit("V2 already exists; this part is not re-runnable.")
    d = db()
    doc_url = f"{APP}/documents/{st['doc_id']}"

    legal = sc.context(browser, "legal", INSIDE)
    sc.login(legal, "legal")
    legal.goto(doc_url)
    legal.get_by_role("button", name="Request amendment").wait_for()
    with sc.beat(legal, "k1", "Amendment: documents are never edited in place; each version is a new immutable record"):
        legal.locator("main").get_by_text("ACTIVE", exact=True).first.hover()
    with sc.beat(legal, "k2", "Legal Officer on the ACTIVE lease: Request amendment (geofenced: location checked)", geo=True):
        legal.get_by_role("button", name="Request amendment").click()
        legal.locator("main").get_by_text("Location reading").first.wait_for()
        legal.locator("main").get_by_text("Location reading").first.hover()
    with sc.beat(legal, "k3", "A reason is required. The document moves to AMENDMENT REQUESTED", geo=True):
        legal.locator("main textarea").fill(REASON)
        legal.get_by_role("button", name="Request amendment").click()
        legal.get_by_text("Amendment approved for a new version").wait_for()
        legal.goto(doc_url)
        legal.locator("main").get_by_text("AMENDMENT REQUESTED", exact=True).first.wait_for()

    staff = sc.context(browser, "staff", INSIDE)
    sc.login(staff, "staff")
    staff.goto(doc_url)
    staff.get_by_role("button", name="Upload amended version").wait_for()
    with sc.beat(staff, "k4", "Authorized Staff uploads the amended file (V2); title, type and classification are copied", geo=True):
        staff.get_by_role("button", name="Upload amended version").click()
        staff.get_by_text("Amendment approved for a new version").wait_for()
        staff.set_input_files("input[type=file]", str(PDF2))
        staff.get_by_role("button", name="Upload new version").click()
        staff.wait_for_url(doc_url, timeout=40000)
        staff.locator("main").get_by_text("DRAFT", exact=True).first.wait_for()
    v1, v2 = supp.versions(st["doc_id"])
    assert v2["version_no"] == 2 and v2["prev_version_hash"] == v1["sha256"]
    save_state(version_id_v2=str(v2["_id"]), sha_v2=v2["sha256"])
    staff.get_by_role("button", name="Submit for review").wait_for()
    with sc.beat(staff, "k5", "V2 starts as DRAFT; its uploader submits it: status SUBMITTED"):
        staff.get_by_role("button", name="Submit for review").click()
        staff.locator("main").get_by_text("SUBMITTED", exact=True).first.wait_for()
    sc.close_role("staff")

    rev = sc.context(browser, "reviewer", INSIDE)
    sc.login(rev, "reviewer")
    rev.goto(doc_url)
    rev.get_by_role("button", name="Review", exact=True).wait_for()
    with sc.beat(rev, "k6", "Three-person rule again: the Reviewing Officer reviews V2 -> PENDING APPROVAL"):
        rev.get_by_role("button", name="Review", exact=True).click()
        rev.fill("textarea", "Amended clause checked. No personal data. Approved for the next step.")
        rev.get_by_role("button", name="Approve review").click()
        rev.locator("main").get_by_text("PENDING APPROVAL", exact=True).first.wait_for()
    sc.close_role("reviewer")

    sc.close_role("legal")


run_scene("scene11_amendment", "Scene 11 - Amendment: version two", "s11", main)
