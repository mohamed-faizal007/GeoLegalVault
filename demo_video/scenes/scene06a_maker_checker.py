"""Scene 6a: the review step, and the self-approval block (negative case on Doc B). No transaction is sent."""
import re
import time

from common import *
import supp

PDF = VID / "samples" / "DEMO_Lease_Agreement_v1.pdf"
TITLE_B = f"DEMO-{DATE}-Doc B maker-checker"


def main(sc, browser):
    st = load_state()
    legal = sc.context(browser, "legal", INSIDE)
    sc.say(legal, "Legal Officer signs in and uploads a second document (Doc B)", "This shows the rule: the person who uploaded cannot approve.", geo=True)
    sc.login(legal, "legal")
    legal.goto(f"{APP}/documents/upload")
    legal.wait_for_timeout(2500)
    legal.fill("#upload-title", TITLE_B)
    legal.fill("#upload-doc-type", "LEASE")
    legal.select_option("#upload-classification", "CONFIDENTIAL")
    legal.set_input_files("input[type=file]", str(PDF))
    legal.get_by_role("button", name="Upload", exact=True).click()
    legal.wait_for_url(re.compile(r".*/documents/[0-9a-f]{24}$"), timeout=30000)
    doc_b = legal.url.rsplit("/", 1)[1]
    save_state(doc_b_id=doc_b, doc_b_title=TITLE_B)
    legal.wait_for_timeout(2500)
    legal.get_by_role("button", name="Submit for review").click()
    legal.wait_for_timeout(3500)
    sc.say(legal, "Doc B is SUBMITTED (uploaded and submitted by the Legal Officer)")

    rev = sc.context(browser, "reviewer", INSIDE)
    sc.say(rev, "Reviewing Officer signs in: a different person reviews both documents")
    sc.login(rev, "reviewer")
    for label, did in (("the main lease document", st["doc_id"]), ("Doc B", doc_b)):
        rev.goto(f"{APP}/documents/{did}")
        rev.wait_for_timeout(2500)
        sc.say(rev, f"Reviewer opens {label}: status SUBMITTED, a Review button is available")
        rev.get_by_role("button", name="Review", exact=True).click()
        rev.wait_for_timeout(1500)
        rev.fill("textarea", "Content checked. No personal data. Approved for the next step.")
        rev.get_by_role("button", name="Approve review").click()
        rev.wait_for_timeout(4000)
        sc.say(rev, f"Review passed for {label}: status PENDING_APPROVAL", "Review is not the blockchain step. Approval is.")
        rev.wait_for_timeout(3500)

    legal.goto(f"{APP}/documents/{doc_b}")
    legal.wait_for_timeout(3000)
    sc.say(legal, "Legal Officer reopens Doc B: no Approve button, because they uploaded it",
           "The screen hides the button, but the real rule is enforced by the server.")
    legal.wait_for_timeout(6000)

    # Real API call as the Legal Officer to approve their own upload (inside the zone).
    status, tok = api("POST", "/auth/login", body={"email": EMAILS["legal"], "password": demo_password()})
    hdr = {"X-Geo-Lat": "11.67", "X-Geo-Lng": "78.15", "X-Geo-Accuracy": "20", "X-Geo-Timestamp": str(time.time())}
    s2, resp = api("POST", f"/documents/{doc_b}/approve", token=tok["access_token"], headers=hdr)
    sc.say(legal, "Supplementary view: a real API call where the uploader tries to approve their own document")
    show_text(legal, "POST /api/v1/documents/<Doc B id>/approve  as the uploader, from inside the zone",
              f"HTTP {s2}\n{json.dumps(resp, indent=2)}\n\n(Sent directly to the API because the UI offers no such button. "
              "The order is: token, role, location, then the maker-checker rule.)")
    legal.wait_for_timeout(12000)


run_scene("scene06a_maker_checker", "Scene 6a - Review and maker-checker", main)
