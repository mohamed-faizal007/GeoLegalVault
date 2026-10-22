"""Scene 12, last beat: a below-clearance viewer asking for the download gets a 404.

The enforcement order is token -> role -> ZONE -> document/clearance, so the throwaway PUBLIC user (created with no zone)
is first refused at the zone step (GEOFENCE_DENIED). To reach the clearance check the Administrator assigns the HQ zone
to the throwaway user (a change to this demo-created user only; its clearance stays PUBLIC). Done through the real
PATCH /users API as the harness, and stated on screen.
"""
from common import *


def main(sc, browser):
    st = load_state()
    d = db()
    viewer_row = d.users.find_one({"email": st["viewer_email"]})
    fence = d.geofences.find_one({"active": True})
    admin_tok = token_for(EMAILS["admin"], demo_password())
    s, _ = api("PATCH", f"/users/{viewer_row['_id']}", token=admin_tok, body={"assigned_geofence_ids": [str(fence["_id"])]})
    assert s == 200, f"assigning the zone to the throwaway user failed: HTTP {s}"
    assert d.users.find_one({"email": st["viewer_email"]})["clearance"] == "PUBLIC"

    tok = token_for(st["viewer_email"], st["viewer_password"])
    s404, body404 = api("GET", f"/documents/{st['doc_id']}/download", token=tok, headers=geo_headers(INSIDE))
    assert s404 == 404, f"expected 404 for the below-clearance viewer, got {s404}"
    viewer = sc.context(browser, "viewer", INSIDE)
    sc.login(viewer, "viewer", password=st["viewer_password"], email=st["viewer_email"])
    with sc.beat(viewer, "k6", "Supplementary view: the PUBLIC viewer, inside an assigned zone, asking for the download gets a 404"):
        show_supp(viewer, "GET /api/v1/documents/<id>/download as the PUBLIC throwaway viewer, from inside the zone",
                  ["Setup (harness): the Administrator assigned the HQ zone to this throwaway user (clearance still PUBLIC),",
                   "so the zone check passes and the clearance check is reached. Order: token, role, zone, then clearance.", "",
                   f"HTTP {s404}   {json.dumps(body404)}", "",
                   "Same answer as a document that does not exist: no link is issued, nothing is served.",
                   "The refused attempt is audited as ACCESS_DENIED."],
                  highlight=["HTTP 404", "document_not_found"], font=27)
    sc.close_role("viewer")
    save_state(viewer_zone_assigned=True)


run_scene("scene12b_clearance_404", "Scene 12 - Download the current version", "s12", main)
