"""Scene 3: Administrator views the geofence zones and creates a throwaway low-clearance user."""
from common import *


def main(sc, browser):
    p = sc.context(browser, "admin", INSIDE)
    sc.say(p, "Administrator signs in")
    sc.login(p, "admin")
    p.goto(f"{APP}/admin")
    p.wait_for_timeout(2000)

    sc.say(p, "Admin Panel: Geofences", "A zone is a polygon of [longitude, latitude] points. The server tests every request against it.")
    p.get_by_role("button", name="Geofences", exact=True).click()
    p.wait_for_timeout(5000)

    sc.say(p, "Admin Panel: Users", "Create a throwaway account. New users start at the lowest clearance, PUBLIC.")
    p.get_by_role("button", name="Users", exact=True).click()
    p.wait_for_timeout(2000)
    pw = new_password()
    email = f"demo-viewer-{DATE}@geolegalvault.demo"
    save_state(viewer_email=email, viewer_password=pw)
    p.fill("input[placeholder=Email]", email)
    p.fill("input[placeholder='Temporary password']", pw)
    p.fill("input[placeholder='Full name']", f"DEMO-{DATE} Viewer")
    p.locator("form select").first.select_option("AUDITOR")
    p.wait_for_timeout(2500)
    sc.say(p, "Create user: role AUDITOR, clearance PUBLIC (the default). Password field is masked.")
    p.get_by_role("button", name="Create user").click()
    p.wait_for_timeout(4000)
    sc.say(p, "User created. This account is used later to show a hidden document and the login lockout.")
    p.mouse.wheel(0, 700)
    p.wait_for_timeout(5000)


run_scene("scene03_admin", "Scene 3 - Admin: zones and users", main)
