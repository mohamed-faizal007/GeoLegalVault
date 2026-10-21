"""Scene 4: positive upload inside the zone as Authorized Staff, then submit for review."""
import re

from common import *
import supp

TITLE = f"DEMO-{DATE}-Lease Agreement"
PDF = VID / "samples" / "DEMO_Lease_Agreement_v1.pdf"


def main(sc, browser):
    p = sc.context(browser, "staff", INSIDE)
    sc.say(p, "Authorized Staff signs in", geo=True)
    sc.login(p, "staff")
    p.goto(f"{APP}/documents/upload")
    p.wait_for_timeout(2500)
    sc.say(p, "Upload form. The page reads the browser location: inside the HQ zone", geo=True)
    p.fill("#upload-title", TITLE)
    p.fill("#upload-doc-type", "LEASE")
    p.select_option("#upload-classification", "CONFIDENTIAL")
    p.set_input_files("input[type=file]", str(PDF))
    p.wait_for_timeout(2500)
    sc.say(p, "Click Upload. Server order: token, role, location, file checks, store, hash, audit", geo=True)
    p.get_by_role("button", name="Upload", exact=True).click()
    p.wait_for_url(re.compile(r".*/documents/[0-9a-f]{24}$"), timeout=30000)
    p.wait_for_timeout(3000)
    doc_id = p.url.rsplit("/", 1)[1]
    body = p.inner_text("body")
    sha = re.search(r"\b[0-9a-f]{64}\b", body)
    save_state(doc_id=doc_id, doc_title=TITLE, sha_v1=sha.group(0) if sha else None)
    sc.say(p, "Uploaded. Status DRAFT. The SHA-256 fingerprint was computed by the server")
    p.wait_for_timeout(5000)

    sc.say(p, "Supplementary view: what the upload wrote (MongoDB + private storage)")
    show_text(p, "documents, document_versions and the stored object", supp.doc_view(doc_id))
    p.wait_for_timeout(14000)

    p.goto(f"{APP}/documents/{doc_id}")
    p.wait_for_timeout(2500)
    sc.say(p, "The uploader submits the document for review", "Only the uploader of the current version may submit it.")
    p.get_by_role("button", name="Submit for review").click()
    p.wait_for_timeout(4000)
    sc.say(p, "Status is now SUBMITTED. The uploader has no Review or Approve button")
    p.wait_for_timeout(5000)


run_scene("scene04_upload", "Scene 4 - Upload inside the zone", main)
