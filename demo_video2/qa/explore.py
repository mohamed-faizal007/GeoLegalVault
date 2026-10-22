import sys
sys.path.insert(0, "scenes")
from common import *
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch()
    def ctxp(role):
        c = b.new_context(viewport={"width":1920,"height":1080}, geolocation=INSIDE, permissions=["geolocation"])
        c.add_init_script(INIT_JS)
        p = c.new_page(); p.goto(f"{APP}/login"); p.fill("#email", EMAILS[role]); p.fill("#password", demo_password()); p.click("button[type=submit]")
        p.wait_for_url(lambda u: "/login" not in u); p.wait_for_timeout(2500); return p
    p = ctxp("staff"); p.screenshot(path="qa/x_staff_dash.png")
    p.goto(f"{APP}/documents"); p.wait_for_timeout(2500); p.screenshot(path="qa/x_staff_repo.png")
    p.goto(f"{APP}/documents/upload"); p.wait_for_timeout(2500); p.screenshot(path="qa/x_upload.png")
    a = ctxp("admin"); a.screenshot(path="qa/x_admin_dash.png")
    a.goto(f"{APP}/admin"); a.wait_for_timeout(2000); a.screenshot(path="qa/x_admin_users.png")
    a.get_by_role("button", name="Geofences", exact=True).click(); a.wait_for_timeout(2000); a.screenshot(path="qa/x_admin_fence.png")
    u = ctxp("auditor"); u.goto(f"{APP}/audit"); u.wait_for_timeout(3000); u.screenshot(path="qa/x_audit.png")
    u.goto(f"{APP}/admin"); u.wait_for_timeout(3000); u.screenshot(path="qa/x_reports.png")
    b.close()
