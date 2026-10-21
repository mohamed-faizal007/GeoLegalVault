"""Scene 6a2: just the supplementary clip for the self-approval block (title fix of scene 6a's last step)."""
import time

from common import *


def main(sc, browser):
    st = load_state()
    p = sc.context(browser, "legal", INSIDE)
    sc.say(p, "Legal Officer is the uploader of Doc B and tries to approve it anyway", geo=True)
    sc.login(p, "legal")
    p.goto(f"{APP}/documents/{st['doc_b_id']}")
    p.wait_for_timeout(5000)
    status, tok = api("POST", "/auth/login", body={"email": EMAILS["legal"], "password": demo_password()})
    hdr = {"X-Geo-Lat": "11.67", "X-Geo-Lng": "78.15", "X-Geo-Accuracy": "20", "X-Geo-Timestamp": str(time.time())}
    s2, resp = api("POST", f"/documents/{st['doc_b_id']}/approve", token=tok["access_token"], headers=hdr)
    sc.say(p, "Supplementary view: a real API call where the uploader tries to approve their own document")
    show_text(p, "POST /api/v1/documents/<Doc B id>/approve   as the uploader, from inside the zone",
              f"HTTP {s2}\n{json.dumps(resp, indent=2)}\n\n(Sent directly to the API because the UI offers no such button. "
              "Order of checks: token, role, location, then the maker-checker rule.)")
    p.wait_for_timeout(11000)


run_scene("scene06a2_selfapprove_api", "Scene 6 - Self-approval blocked", main)
