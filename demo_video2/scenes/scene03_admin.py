"""Scene 3: Administrator views the zone and creates the throwaway PUBLIC-clearance user (used in scenes 8, 12, 15)."""
from common import *

EMAIL = f"demo-viewer-{DATE}@geolegalvault.demo"
NAME = f"DEMO-{DATE} Viewer"


def main(sc, browser):
    p = sc.context(browser, "admin", INSIDE)
    sc.login(p, "admin")
    p.goto(f"{APP}/admin")
    p.get_by_role("button", name="Geofences", exact=True).wait_for()
    pw = new_password()
    save_state(viewer_email=EMAIL, viewer_password=pw, viewer_name=NAME)

    with sc.beat(p, "k1", "Admin Panel: the Geofences tab lists the approved zones"):
        p.get_by_role("button", name="Geofences", exact=True).click()
        p.wait_for_timeout(800)
    with sc.beat(p, "k2", "A zone is a polygon of [longitude, latitude] pairs; the server tests every request against it",
                 "The form's centre preview is a visual aid only. The zone itself is the HQ Campus row."):
        p.get_by_text("Approximate centre").first.hover()
        p.wait_for_timeout(5000)
        p.get_by_text("HQ Campus (demo)").first.hover()
    with sc.beat(p, "k3", "Users tab: people shown by name, with role and clearance"):
        p.get_by_role("button", name="Users", exact=True).click()
        p.wait_for_timeout(1000)
        p.mouse.wheel(0, 500)
        p.wait_for_timeout(800)
        p.get_by_text("Legal_Officer", exact=True).first.hover()
        p.mouse.wheel(0, -600)
    with sc.beat(p, "k4", "Create a throwaway account: role AUDITOR, clearance PUBLIC (the default). The password field is masked"):
        p.fill("input[placeholder=Email]", EMAIL)
        p.fill("input[placeholder='Temporary password']", pw)
        p.fill("input[placeholder='Full name']", NAME)
        p.locator("form select").first.select_option("AUDITOR")
        p.wait_for_timeout(600)
    with sc.beat(p, "k5", "User created. It is used later for a hidden document and the login protection"):
        p.get_by_role("button", name="Create user").click()
        p.get_by_text(EMAIL).wait_for()
        p.get_by_text(EMAIL).scroll_into_view_if_needed()
        p.get_by_text(EMAIL).hover()
        p.wait_for_timeout(1200)
    sc.close_role("admin")


run_scene("scene03_admin", "Scene 3 - Admin: zones and users", "s03", main)
