"""Scene 2: login and roles. Three real logins in three separate browser contexts."""
from common import *


def main(sc, browser):
    staff = sc.context(browser, "staff", INSIDE)
    sc.say(staff, "Authorized Staff signs in", "Five roles. Each person sees only what their role allows.", geo=True)
    sc.login(staff, "staff")
    staff.wait_for_timeout(3500)
    sc.say(staff, "Authorized Staff: sidebar has Upload, but no Admin Panel and no Audit Logs",
           "Role and clearance are checked by the server on every request, not by this menu.")
    staff.wait_for_timeout(5000)

    legal = sc.context(browser, "legal", INSIDE)
    sc.say(legal, "Legal Officer signs in (a different person, a different browser session)", geo=True)
    sc.login(legal, "legal")
    legal.wait_for_timeout(5000)

    admin = sc.context(browser, "admin", INSIDE)
    sc.say(admin, "Administrator signs in", "Administrators manage users and zones. They cannot upload, review or approve.")
    sc.login(admin, "admin")
    admin.wait_for_timeout(2500)
    sc.say(admin, "Administrator: Admin Panel and Audit Logs appear; Upload does not",
           "Separation of duties: the person who manages the system cannot approve documents.")
    admin.wait_for_timeout(5000)


run_scene("scene02_login_roles", "Scene 2 - Login and roles", main)
