from common import *


def main(sc, browser):
    p = sc.context(browser, "staff", INSIDE)
    sc.say(p, "Smoke test: login as Authorized Staff", geo=True)
    sc.login(p, "staff")
    p.goto(f"{APP}/geofence-status")
    p.wait_for_timeout(3000)
    p.screenshot(path=str(sc.dir / "geo.png"))
    print(p.inner_text("body")[:500])


run_scene("scene00_smoke", "Smoke", main)
