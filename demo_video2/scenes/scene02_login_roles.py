"""Scene 2: login, roles, clearance, names. Three real logins in three separate browser contexts (read-only)."""
from common import *


def main(sc, browser):
    staff = sc.context(browser, "staff", INSIDE)
    staff.goto(f"{APP}/login")
    staff.wait_for_selector("#email")
    with sc.beat(staff, "k1", "Five roles. Each person sees only what their role allows.", geo=True):
        staff.fill("#email", EMAILS["staff"])
        staff.fill("#password", demo_password())
    with sc.beat(staff, "k2", "Authorized Staff: the welcome line shows a name; menu has Upload, no Admin Panel, no Audit Logs"):
        staff.click("button[type=submit]")
        staff.wait_for_url(lambda u: "/login" not in u, timeout=20000)
        staff.get_by_text("Welcome").first.wait_for()
        staff.wait_for_timeout(1500)
    with sc.beat(staff, "k3", "Counts come from the server and differ by clearance; archived documents are left out"):
        staff.get_by_text("Total documents").first.hover()
        staff.wait_for_timeout(800)
    sc.close_role("staff")

    legal = sc.context(browser, "legal", INSIDE)
    legal.goto(f"{APP}/login")
    legal.wait_for_selector("#email")
    legal.fill("#email", EMAILS["legal"])
    legal.fill("#password", demo_password())
    with sc.beat(legal, "k4", "Legal Officer signs in: a different person, a separate browser session; higher clearance, more documents"):
        legal.click("button[type=submit]")
        legal.wait_for_url(lambda u: "/login" not in u, timeout=20000)
        legal.get_by_text("Welcome").first.wait_for()
        legal.wait_for_timeout(1200)
        legal.get_by_text("Total documents").first.hover()
    sc.close_role("legal")

    admin = sc.context(browser, "admin", INSIDE)
    admin.goto(f"{APP}/login")
    admin.wait_for_selector("#email")
    admin.fill("#email", EMAILS["admin"])
    admin.fill("#password", demo_password())
    with sc.beat(admin, "k5", "Administrator: Admin Panel and Audit Logs appear; Upload does not"):
        admin.click("button[type=submit]")
        admin.wait_for_url(lambda u: "/login" not in u, timeout=20000)
        admin.get_by_text("Welcome").first.wait_for()
        admin.wait_for_timeout(1500)
        admin.get_by_text("Admin Panel").first.hover()
    with sc.beat(admin, "k6", "Clearance: Public < Internal < Confidential < Restricted < Top Secret. The server checks on every request"):
        admin.goto(f"{APP}/admin")
        admin.wait_for_timeout(1500)
    sc.close_role("admin")


run_scene("scene02_login_roles", "Scene 2 - Login, roles, clearance", "s02", main)
