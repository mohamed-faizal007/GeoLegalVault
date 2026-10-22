"""Scene 5: negative uploads. Outside the zone, then inside but too imprecise. Fail-closed. Nothing should be stored."""
import datetime as dt

from common import *
import supp

PDF = VID / "samples" / "DEMO_Lease_v1.pdf"


def fill(p, title):
    p.fill("#upload-title", title)
    p.fill("#upload-doc-type", "LEASE")
    p.select_option("#upload-classification", "INTERNAL")
    p.set_input_files("input[type=file]", str(PDF))


def main(sc, browser):
    n_docs = db().documents.count_documents({})
    since = dt.datetime.utcnow()
    p = sc.context(browser, "staff", OUTSIDE)
    sc.login(p, "staff")
    p.goto(f"{APP}/documents/upload")
    p.locator("main").get_by_text("Location reading").first.wait_for()
    p.wait_for_timeout(1200)

    with sc.beat(p, "k1", "Authorized Staff, browser location about 100 km OUTSIDE the zone", geo=True):
        p.locator("main").get_by_text("Location reading").first.hover()
    with sc.beat(p, "k2", "Upload from outside the zone: refused with GEOFENCE_DENIED (HTTP 403). Nothing is stored", geo=True):
        fill(p, f"DEMO-{DATE}-Outside attempt")
        p.get_by_role("button", name="Upload", exact=True).click()
        p.locator("main").get_by_text("GEOFENCE_DENIED").first.wait_for()
        p.wait_for_timeout(800)
    with sc.beat(p, "k3", "Now the location is inside the zone but very imprecise: accuracy 500 m", geo=True):
        sc.ctxs["staff"].set_geolocation(POOR)
        p.locator("main").get_by_role("button", name="refresh", exact=True).click()
        p.locator("main").get_by_text("±500m").first.wait_for()
    with sc.beat(p, "k4", "Refused: LOCATION_LOW_CONFIDENCE (HTTP 422). Fail-closed; this server allows up to 300 m", geo=True):
        fill(p, f"DEMO-{DATE}-Imprecise attempt")
        p.get_by_role("button", name="Upload", exact=True).click()
        p.locator("main").get_by_text("LOCATION_LOW_CONFIDENCE").first.wait_for()
        p.wait_for_timeout(800)
    with sc.beat(p, "k5", "Supplementary view: the zone denial is in audit_logs; LOCATION_LOW_CONFIDENCE is not"):
        show_supp(p, "audit_logs: the GEOFENCE_DENIED row for the outside-zone attempt",
                  supp.audit_lines(actions=["GEOFENCE_DENIED"], limit=2, since=since),
                  highlight=["GEOFENCE_DENIED"],
                  note="LOCATION_LOW_CONFIDENCE is refused before the zone check and goes to the application log, not to audit_logs.")
    with sc.beat(p, "k6", "Geofence Status page: browser location is a policy input, not a security guarantee"):
        p.goto(f"{APP}/geofence-status")
        p.locator("main").get_by_text("policy input").first.wait_for()
        p.locator("main").get_by_text("policy input").first.hover()
    sc.close_role("staff")
    assert db().documents.count_documents({}) == n_docs, "a refused upload must not create a document"


run_scene("scene05_geofence_denied", "Scene 5 - Upload refused (fail-closed)", "s05", main)
