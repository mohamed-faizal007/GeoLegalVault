"""Scene 5: negative uploads. Outside the zone, then accurate-but-too-imprecise location. Fail-closed."""
from common import *
import supp

PDF = VID / "samples" / "DEMO_Lease_Agreement_v1.pdf"


def fill(p, title):
    p.fill("#upload-title", title)
    p.fill("#upload-doc-type", "LEASE")
    p.select_option("#upload-classification", "CONFIDENTIAL")
    p.set_input_files("input[type=file]", str(PDF))


def main(sc, browser):
    p = sc.context(browser, "staff", OUTSIDE)
    sc.say(p, "Authorized Staff signs in. Browser location is about 100 km OUTSIDE the zone", geo=True)
    sc.login(p, "staff")
    p.goto(f"{APP}/documents/upload")
    p.wait_for_timeout(3000)
    fill(p, f"DEMO-{DATE}-Outside attempt")
    sc.say(p, "Try to upload from outside the zone", "The server decides inside or outside, not the browser.", geo=True)
    p.wait_for_timeout(2000)
    p.get_by_role("button", name="Upload", exact=True).click()
    p.wait_for_timeout(5000)
    sc.say(p, "Refused: GEOFENCE_DENIED (HTTP 403). Nothing was stored", geo=True)
    p.wait_for_timeout(6000)

    sc.ctxs["staff"].set_geolocation(POOR)
    sc.say(p, "Now the location is inside the zone but very imprecise: accuracy 500 m", "Fail-closed: a reading that is too vague is refused before the zone is even checked.", geo=True)
    p.get_by_text("refresh", exact=True).first.click()
    p.wait_for_timeout(3500)
    fill(p, f"DEMO-{DATE}-Imprecise attempt")
    p.get_by_role("button", name="Upload", exact=True).click()
    p.wait_for_timeout(5000)
    sc.say(p, "Refused: LOCATION_LOW_CONFIDENCE (HTTP 422). This machine allows up to 300 m", geo=True)
    p.wait_for_timeout(6000)

    sc.say(p, "Supplementary view: the audit log entry for the zone denial")
    show_text(p, "audit_logs: GEOFENCE_DENIED is recorded with the claimed position",
              supp.audit_view(actions=["GEOFENCE_DENIED"], limit=3) +
              "\n\nA LOCATION_LOW_CONFIDENCE refusal happens before the zone check and is written to the application log, not to audit_logs.")
    p.wait_for_timeout(9000)


run_scene("scene05_geofence_denied", "Scene 5 - Upload refused (fail-closed)", main)
