"""Scene 14: NOT_ANCHORED live on a SEEDED DRAFT (never approved, so nothing was anchored), then one slide that lists all
six outcomes and stays up for the whole narration of the list. Verifying appends one verification_records row and one
audit row to that seeded document; it changes nothing else. ANCHOR_MISSING / FILE_MISSING / CHAIN_UNREACHABLE are not
triggered live (the slide says so)."""
from common import *
from flows import run_verify


def main(sc, browser):
    d = db()
    doc = d.documents.find_one({"title": "Public Notice - Change of Registered Office"})
    assert doc["status"] == "DRAFT"
    v = d.document_versions.find_one({"document_id": doc["_id"]})
    p = sc.context(browser, "legal", INSIDE)
    sc.login(p, "legal")
    p.goto(f"{APP}/verify/{v['_id']}")
    p.get_by_role("button", name="Run verification").wait_for()
    with sc.beat(p, "k1", "Six possible results. One more, live: a seeded DRAFT that was never approved"):
        p.locator("main h1").first.hover()
    with sc.beat(p, "k2", "NOT ANCHORED YET: the file is intact, but there is no blockchain record to compare with"):
        run_verify(p, "NOT ANCHORED")
        p.get_by_text("3-way hash comparison").first.hover()
    sc.close_role("legal")
    for key in ("s1", "s2", "s3", "s4", "s5"):
        sc.slide(key, "outcomes")


run_scene("scene14_outcomes", "Scene 14 - Other verification outcomes", "s14", main)
