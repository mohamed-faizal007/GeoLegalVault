"""Scene 9: verify the genuine file -> VERIFIED (read-only apart from one verification_records row + audit row)."""
from common import *


def main(sc, browser):
    st = load_state()
    p = sc.context(browser, "legal", INSIDE)
    sc.say(p, "Legal Officer opens Integrity Verification for version 1")
    sc.login(p, "legal")
    p.goto(f"{APP}/verify/{st['version_id']}")
    p.wait_for_timeout(4000)
    sc.say(p, "Run verification: read the stored file, hash it, compare with the database and with the chain",
           "Three checks: (1) hash of the bytes now in storage, (2) hash recorded at upload, (3) hash read live from the Sepolia contract.")
    p.get_by_role("button", name="Run verification").click()
    p.get_by_text("3-way hash comparison").wait_for(timeout=60000)
    p.wait_for_timeout(2500)
    sc.say(p, "VERIFIED: all three hashes are identical")
    p.wait_for_timeout(11000)


run_scene("scene09_verify_ok", "Scene 9 - Verify the genuine file", main)
