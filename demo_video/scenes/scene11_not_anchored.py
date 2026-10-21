"""Scene 11: NOT_ANCHORED, shown safely on Doc B (reviewed but never approved, so never anchored)."""
from bson import ObjectId

from common import *


def main(sc, browser):
    st = load_state()
    v = db().document_versions.find_one({"document_id": ObjectId(st["doc_b_id"])})
    p = sc.context(browser, "reviewer", INSIDE)
    sc.say(p, "Reviewing Officer signs in")
    sc.login(p, "reviewer")
    p.goto(f"{APP}/verify/{v['_id']}")
    p.wait_for_timeout(3500)
    sc.say(p, "Verify Doc B: it passed review but was never approved, so nothing was ever anchored")
    p.get_by_role("button", name="Run verification").click()
    p.get_by_text("3-way hash comparison").wait_for(timeout=60000)
    p.wait_for_timeout(2500)
    sc.say(p, "NOT_ANCHORED: the file is intact, but there is no blockchain record to compare with",
           "This is not an error and not a tamper alarm. It only means approval has not happened yet.")
    p.wait_for_timeout(12000)
    p.screenshot(path=str(sc.dir / "not_anchored.png"))


run_scene("scene11_not_anchored", "Scene 11 - NOT_ANCHORED", main)
