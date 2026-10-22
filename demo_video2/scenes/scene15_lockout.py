"""Scene 15: login protection. ONLY ever the throwaway demo account (5 wrong passwords = a one-minute pause)."""
import json

from common import *


def main(sc, browser):
    st = load_state()
    email = st["viewer_email"]
    assert email.startswith("demo-viewer-"), "the lockout scene may only use the throwaway account"
    p = sc.context(browser, "viewer", None)
    p.goto(f"{APP}/login")
    p.wait_for_selector("#email")
    with sc.beat(p, "k1", "Login protection: wrong passwords on the throwaway account only"):
        p.fill("#email", email)
    steps = [("k2", 1), ("k3", 2), ("k4", 3), ("k5", 4), ("k6", 5)]
    for key, n in steps:
        with sc.beat(p, key, f"Wrong password: the page shows 'Attempt {n} of 5'" + (" and the pause message" if n == 5 else "")):
            p.fill("#password", f"not-the-password-{n}")
            p.click("button[type=submit]")
            p.get_by_role("alert").get_by_text(f"Attempt {n} of 5").wait_for()
    with sc.beat(p, "k7", "The next try is refused outright: Too many attempts"):
        p.fill("#password", "not-the-password-6")
        p.click("button[type=submit]")
        p.get_by_role("alert").get_by_text("Too many attempts").wait_for()
    docs = [x for x in db().login_rate_limits.find() if email in json.dumps(x, default=str)]
    assert docs, "no login_rate_limits row found for the throwaway account"
    lines = ["db.login_rate_limits  (the row for the throwaway account only)"]
    for x in docs:
        x.pop("_id", None)
        lines += [f"  {k:<14} {v}" for k, v in x.items()]
    with sc.beat(p, "k8", "Supplementary view: the login_rate_limits counter for this email, and when the pause ends"):
        show_supp(p, "MongoDB: login_rate_limits", lines + ["", "5 failures -> the account is paused for about a minute."],
                  highlight=[email])
    sc.close_role("viewer")


run_scene("scene15_lockout", "Scene 15 - Login protection", "s15", main)
