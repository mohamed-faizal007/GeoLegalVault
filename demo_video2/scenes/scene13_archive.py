"""Scene 13: archive the fresh document from ACTIVE (Legal Officer; no reason field; not geofenced). Archives ONLY the fresh
document (never a seeded one). Not reversible in the app: there is no restore route. Not re-runnable."""
from bson import ObjectId

from common import *


def main(sc, browser):
    st = load_state()
    d = db()
    doc = d.documents.find_one({"_id": ObjectId(st["doc_id"])})
    assert doc["title"] == TITLE and doc["status"] == "ACTIVE", "only the ACTIVE fresh document may be archived"
    p = sc.context(browser, "legal", INSIDE)
    sc.login(p, "legal")
    p.goto(f"{APP}/documents")
    box = p.get_by_placeholder("Search title or tags…")
    box.wait_for()
    box.fill(TITLE)
    p.locator("main").get_by_text(TITLE).first.wait_for()

    with sc.beat(p, "k1", "Document Repository (default list): the ACTIVE lease is listed"):
        p.locator("main").get_by_text(TITLE).first.hover()
    with sc.beat(p, "k2", "Open it and choose Archive: no reason field, not geofenced"):
        p.locator("main").get_by_text(TITLE).first.click()
        p.get_by_role("button", name="Archive", exact=True).wait_for()
        p.get_by_role("button", name="Archive", exact=True).hover()
        p.get_by_role("button", name="Archive", exact=True).click()
    with sc.beat(p, "k3", "Status is now ARCHIVED"):
        p.locator("main").get_by_text("ARCHIVED", exact=True).first.wait_for()
        p.locator("main").get_by_text("ARCHIVED", exact=True).first.hover()
    with sc.beat(p, "k4", "Gone from the default Dashboard and Repository (archived documents are left out)"):
        p.goto(f"{APP}/")
        p.get_by_text("Total documents").first.wait_for()
        p.wait_for_timeout(2000)
        p.get_by_text("Total documents").first.hover()
        p.goto(f"{APP}/documents")
        box = p.get_by_placeholder("Search title or tags…")
        box.fill(f"DEMO-{DATE}")
        p.wait_for_timeout(2500)
    with sc.beat(p, "k5", "Repository filter Archived: the lease appears"):
        p.locator("main select").first.select_option("ARCHIVED")
        p.locator("main").get_by_text(TITLE).first.wait_for()
        p.locator("main").get_by_text(TITLE).first.hover()
    with sc.beat(p, "k6", "An archived document keeps all versions, anchors and files; the app offers no undo"):
        p.locator("main").get_by_text(TITLE).first.click()
        p.get_by_role("link", name="Version history").wait_for()
        p.get_by_role("link", name="Version history").hover()
    sc.close_role("legal")
    after = d.documents.find_one({"_id": doc["_id"]})
    save_state(archived=True, status_after_archive=after["status"])
    print("status after archive:", after["status"])


run_scene("scene13_archive", "Scene 13 - Archive", "s13", main)
