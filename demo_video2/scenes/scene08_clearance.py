"""Scene 8: a hidden document is a 404, never a 403. The PUBLIC throwaway viewer on the INTERNAL fresh document, and the
Administrator (INTERNAL) on a seeded CONFIDENTIAL document. Read-only apart from the ACCESS_DENIED audit rows."""
import datetime as dt
import re

from common import *
import supp

NOT_FOUND = re.compile(r"couldn.t be found|not found", re.I)


def main(sc, browser):
    st = load_state()
    since = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    conf = db().documents.find_one({"title": "Commercial Lease - Anna Salai Warehouse Unit 4"})
    assert conf and conf["classification"] == "CONFIDENTIAL"
    viewer = sc.context(browser, "viewer", INSIDE)
    sc.login(viewer, "viewer", password=st["viewer_password"], email=st["viewer_email"])
    viewer.goto(f"{APP}/documents")
    viewer.get_by_placeholder("Search title or tags…").wait_for()
    viewer.wait_for_timeout(1500)

    with sc.beat(viewer, "k1", "Throwaway user (role Auditor, clearance PUBLIC): the lease is INTERNAL"):
        viewer.locator("main h1").first.hover()
    with sc.beat(viewer, "k2", "Document Repository: the INTERNAL lease is not listed; the server filters in the query"):
        viewer.get_by_placeholder("Search title or tags…").fill(f"DEMO-{DATE}")
        viewer.wait_for_timeout(2500)
    with sc.beat(viewer, "k3", "Direct link to the real document id: plain 'not found' (the UI retries before giving up)"):
        viewer.goto(f"{APP}/documents/{st['doc_id']}")
        with sc.trimmed():
            viewer.locator("main").get_by_text(NOT_FOUND).first.wait_for(timeout=60000)
        viewer.locator("main").get_by_text(NOT_FOUND).first.hover()

    t = token_for(st["viewer_email"], st["viewer_password"])
    real = api("GET", f"/documents/{st['doc_id']}", token=t)
    fake = api("GET", "/documents/000000000000000000000000", token=t)
    with sc.beat(viewer, "k4", "Supplementary view: a hidden document and a made-up id give the identical 404"):
        show_supp(viewer, "GET /api/v1/documents/<id> as the PUBLIC user",
                  ["Real document (INTERNAL, exists):", f"  HTTP {real[0]}   {json.dumps(real[1])}", "",
                   "Made-up id (does not exist):", f"  HTTP {fake[0]}   {json.dumps(fake[1])}", "",
                   "Same status, same body. A 403 would have confirmed that the document exists."],
                  highlight=["HTTP 404", "document_not_found"])
    sc.close_role("viewer")

    admin = sc.context(browser, "admin", INSIDE)
    sc.login(admin, "admin")
    admin.goto(f"{APP}/documents/{conf['_id']}")
    with sc.beat(admin, "k5", "Administrator (clearance INTERNAL) opens a seeded CONFIDENTIAL document: also a real 404"):
        with sc.trimmed():
            admin.locator("main").get_by_text(NOT_FOUND).first.wait_for(timeout=60000)
        admin.locator("main").get_by_text(NOT_FOUND).first.hover()
    with sc.beat(admin, "k6", "Supplementary view: the refused attempts on documents that exist are audited as ACCESS_DENIED"):
        show_supp(admin, "audit_logs: ACCESS_DENIED rows written during this scene",
                  supp.audit_lines(actions=["ACCESS_DENIED"], limit=5, since=since),
                  highlight=["ACCESS_DENIED"],
                  note="Access control inside the application. It is not encryption.")
    sc.close_role("admin")


run_scene("scene08_clearance", "Scene 8 - Clearance: hidden means 404", "s08", main)
