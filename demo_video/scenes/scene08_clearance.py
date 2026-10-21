"""Scene 8: a PUBLIC-clearance user cannot see a CONFIDENTIAL document; the answer is 404, never 403."""
from common import *
import supp


def main(sc, browser):
    st = load_state()
    p = sc.context(browser, "viewer", INSIDE)
    sc.say(p, "The throwaway user (role Auditor, clearance PUBLIC) signs in")
    sc.login(p, "viewer", password=st["viewer_password"], email=st["viewer_email"])
    p.goto(f"{APP}/documents")
    p.wait_for_timeout(4000)
    sc.say(p, "Document Repository: the CONFIDENTIAL lease is not listed for this user",
           "The server filters in the database query, so a hidden document is never fetched and then dropped.")
    p.get_by_placeholder("Search title or tags…").fill("DEMO-20261021")
    p.wait_for_timeout(5000)
    sc.say(p, "Even a direct link to the real document id shows plain 'not found'")
    p.goto(f"{APP}/documents/{st['doc_id']}")
    p.wait_for_timeout(18000)

    s1, tok = api("POST", "/auth/login", body={"email": st["viewer_email"], "password": st["viewer_password"]})
    t = tok["access_token"]
    real = api("GET", f"/documents/{st['doc_id']}", token=t)
    fake = api("GET", "/documents/000000000000000000000000", token=t)
    sc.say(p, "Supplementary view: the API answers for a hidden document and for a document that does not exist")
    show_text(p, "GET /api/v1/documents/<id> as the PUBLIC user",
              f"Real document, CONFIDENTIAL (exists):\n  HTTP {real[0]}  {json.dumps(real[1])}\n\n"
              f"Made-up id (does not exist):\n  HTTP {fake[0]}  {json.dumps(fake[1])}\n\n"
              "Same status, same body: a 403 would have told the caller the document exists. "
              "The refused attempt on the real document is recorded in audit_logs as ACCESS_DENIED.\n\n"
              + supp.audit_view(actions=["ACCESS_DENIED"], limit=2))
    p.wait_for_timeout(15000)


run_scene("scene08_clearance", "Scene 8 - Clearance: hidden means 404", main)
