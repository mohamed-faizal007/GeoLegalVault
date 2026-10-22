"""Scene 17: the Reports panel as the Auditor (read-only). Ends on the Mismatches card and the ARCHIVED count, both in view."""
from common import *

OUTLINE = """
() => {
  const hl = (el) => { if (el) el.style.cssText += ';outline:4px solid #ffd33d;outline-offset:4px;border-radius:10px'; };
  const cards = [...document.querySelectorAll('main div')].filter(e => /^MISMATCHES \(/i.test((e.firstElementChild || {}).textContent || '') );
  const mm = [...document.querySelectorAll('main p, main span, main div')].find(e => /^Mismatches \(/i.test((e.textContent || '').trim()) && e.children.length === 0);
  if (mm) hl(mm.closest('div[class*=card], div[class*=rounded]') || mm.parentElement);
  const ar = [...document.querySelectorAll('main span, main div, main p')].find(e => (e.textContent || '').trim() === 'ARCHIVED' && e.children.length === 0);
  if (ar) hl(ar.parentElement);
  return [!!mm, !!ar];
}
"""


def main(sc, browser):
    p = sc.context(browser, "auditor", INSIDE)
    sc.login(p, "auditor")
    p.goto(f"{APP}/admin")
    p.get_by_text("Anchors confirmed").first.wait_for()
    p.get_by_text("documents you can access in total").first.wait_for()
    with sc.beat(p, "k1", "Reports panel (the Auditor sees only this tab of the Admin Panel)"):
        p.locator("main h1").first.hover()
    with sc.beat(p, "k2", "Anchors confirmed: the successful Sepolia transactions, including this demo's two"):
        p.get_by_text("Anchors confirmed").first.hover()
    with sc.beat(p, "k3", "The note reconciles the counts: 22 accessible in total, 3 archived; Dashboard and Repository show 19"):
        p.get_by_text("documents you can access in total").first.hover()
    with sc.beat(p, "k4", "Mismatches counts the tamper test; the archived count went up by one"):
        found = p.evaluate(OUTLINE)
        print("outlined (mismatches card, archived row):", found)
        p.mouse.move(1500, 600)
    sc.close_role("auditor")


run_scene("scene17_reports", "Scene 17 - Reports", "s17", main)
