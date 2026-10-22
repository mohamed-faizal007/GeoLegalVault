"""Small UI flows shared by several scenes."""
import time


def run_verify(p, expect: str, timeout: int = 90000):
    """Click Run verification and wait until the result box shows `expect` (the page shows the previous result until the
    fresh one arrives, so waiting for the new headline text is what tells them apart)."""
    p.get_by_role("button", name="Run verification").click()
    p.wait_for_function(
        "t => [...document.querySelectorAll('main [role=status]')].some(e => e.innerText.includes(t))", arg=expect, timeout=timeout)
    p.wait_for_timeout(600)


def wait_active(sc, p, save_state, stuck_key: str, t_click: float, label: str):
    """Wait (trimmed) for the document to become ACTIVE after Approve. If it stays APPROVED because the anchor did not
    confirm inside the request window, STOP: no worker, no retry loop."""
    with sc.trimmed():
        while True:
            txt = p.locator("main").inner_text()
            if p.locator("main").get_by_text("ACTIVE", exact=True).count():
                return
            if "Working" not in txt and p.locator("main").get_by_text("APPROVED", exact=True).count() and time.time() - t_click > 25:
                save_state(**{stuck_key: True})
                raise SystemExit(f"STOP: {label} is APPROVED but the anchor did not confirm in the request window. "
                                 "Not starting the worker and not retrying; report to the user.")
            if time.time() - t_click > 170:
                save_state(**{stuck_key: True})
                raise SystemExit(f"STOP: {label}: no ACTIVE status within 170 s; report to the user.")
            p.wait_for_timeout(1000)
