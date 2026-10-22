"""Scene 4: version one. Authorized Staff uploads the fresh INTERNAL document inside the zone, then submits it.
Creates ONE document (refuses to run if one with this title already exists)."""
import re

from common import *
import supp

PDF = VID / "samples" / "DEMO_Lease_v1.pdf"


def main(sc, browser):
    if db().documents.count_documents({"title": TITLE}):
        raise SystemExit(f"{TITLE!r} already exists in {DEMO_DB}; refusing to upload a second one.")
    p = sc.context(browser, "staff", INSIDE)
    sc.login(p, "staff")
    p.goto(f"{APP}/documents/upload")
    p.locator("main").get_by_text("Location reading").first.wait_for()
    p.wait_for_timeout(1500)

    with sc.beat(p, "k1", "Upload form: the page shows the browser's location reading (inside the HQ zone)", geo=True):
        p.locator("main").get_by_text("Location reading").first.hover()
    with sc.beat(p, "k2", f"Title {TITLE}, type LEASE, classification INTERNAL, a sample PDF"):
        p.fill("#upload-title", TITLE)
        p.fill("#upload-doc-type", "LEASE")
        p.select_option("#upload-classification", "INTERNAL")
        p.set_input_files("input[type=file]", str(PDF))
        p.wait_for_timeout(800)
    with sc.beat(p, "k3", "Upload: server order is token, role, location, file checks, store, hash, audit", geo=True):
        p.get_by_role("button", name="Upload", exact=True).click()
        p.wait_for_url(re.compile(r".*/documents/[0-9a-f]{24}$"), timeout=40000)
        p.get_by_text("DRAFT", exact=True).first.wait_for()
        doc_id = p.url.rsplit("/", 1)[1]
        v = supp.versions(doc_id)[0]
        save_state(doc_id=doc_id, doc_title=TITLE, sha_v1=v["sha256"], version_id=str(v["_id"]), storage_key=v["storage_key"])
        p.locator("main").get_by_text("Owner").first.hover()
    st = load_state()

    with sc.beat(p, "k4", "Supplementary view: the document row and the version row, with the SHA-256 fingerprint highlighted"):
        show_supp(p, "MongoDB: documents and document_versions (after the upload)",
                  supp.doc_version_lines(st["doc_id"]), highlight=[st["sha_v1"]])
    with sc.beat(p, "k5", "Supplementary view: the file is in the private bucket, under a server-made key that contains the hash"):
        show_supp(p, "Private object storage (RustFS dev / Cloudflare R2 prod)",
                  supp.bucket_lines(st["doc_id"]) + [""] + [f"  stored under key:  {st['storage_key']}"],
                  highlight=[f"v1-{st['sha_v1']}"],
                  note="Shared dev bucket: only this document's own object is ever touched by this demo.")
    p.goto(f"{APP}/documents/{st['doc_id']}")
    p.get_by_role("button", name="Submit for review").wait_for()
    with sc.beat(p, "k6", "The uploader submits the document for review: status SUBMITTED"):
        p.get_by_role("button", name="Submit for review").click()
        p.get_by_text("SUBMITTED", exact=True).first.wait_for()
    with sc.beat(p, "k7", "Version History: V1 with its SHA-256 shortened on screen"):
        p.goto(f"{APP}/documents/{st['doc_id']}/versions")
        p.locator("main").get_by_text("SHA-256").first.wait_for()
        p.locator("main").get_by_text("SHA-256").first.hover()
    sc.close_role("staff")


run_scene("scene04_upload", "Scene 4 - Upload version one inside the zone", "s04", main)
