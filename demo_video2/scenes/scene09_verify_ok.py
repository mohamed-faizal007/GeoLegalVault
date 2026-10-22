"""Scene 9: verify the genuine file -> VERIFIED (appends one verification_records row and one audit row)."""
from common import *
from flows import run_verify


def main(sc, browser):
    st = load_state()
    p = sc.context(browser, "legal", INSIDE)
    sc.login(p, "legal")
    p.goto(f"{APP}/verify/{st['version_id']}")
    p.get_by_role("button", name="Run verification").wait_for()

    with sc.beat(p, "k1", "Integrity Verification for version 1 of the lease"):
        p.locator("main h1").first.hover()
    with sc.beat(p, "k2", "Run verification: read the stored file, hash it, compare with the database and with the chain"):
        run_verify(p, "VERIFIED")
    with sc.beat(p, "k3", "VERIFIED: recomputed, stored and on-chain hashes are identical"):
        p.get_by_text("3-way hash comparison").first.hover()
    with sc.beat(p, "k4", "A database change alone, or a storage change alone, cannot produce a false VERIFIED"):
        p.get_by_text("On-chain (Sepolia)").first.hover()
    sc.close_role("legal")


run_scene("scene09_verify_ok", "Scene 9 - Verify the genuine file", "s09", main)
