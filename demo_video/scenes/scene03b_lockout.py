"""Scene 3b: login lockout. ONLY ever uses the throwaway demo account (5 wrong passwords = a one-minute lockout)."""
from common import *


def main(sc, browser):
    st = load_state()
    assert st["viewer_email"].startswith("demo-viewer-"), "lockout scene may only use the throwaway account"
    p = sc.context(browser, "viewer", None)
    sc.say(p, "Login protection: five wrong passwords lock the account for one minute (throwaway account only)")
    for i in range(1, 7):
        sc.say(p, f"Wrong password, attempt {i}")
        p.goto(f"{APP}/login")
        p.fill("#email", st["viewer_email"])
        p.fill("#password", "not-the-password-" + str(i))
        p.click("button[type=submit]")
        p.wait_for_timeout(2500)
    sc.say(p, "Locked out: even the next attempt is refused for a while", "Brute-force guessing is slowed down. Counters are stored in MongoDB (login_rate_limits).")
    p.wait_for_timeout(8000)
    p.screenshot(path=str(sc.dir / "lockout.png"))


run_scene("scene03b_lockout", "Scene 3 - Login lockout", main)
