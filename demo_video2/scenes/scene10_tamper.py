"""Scene 10: save the original V1 bytes, change one byte of THIS document's own stored object with demo/tamper.py,
verify -> MISMATCH, restore the saved bytes, confirm the hash equals the recorded SHA-256, verify -> VERIFIED, then the
Administrator clears the TAMPERED flag ("Clear integrity flag", reason of 10+ characters).

The restore runs even if the scene fails half way (try/finally). The bucket is shared with the dev setup; only the
object under this document's own key is ever written. NOT meant to be re-run after it succeeded.
"""
import hashlib
import subprocess

from common import *
from flows import run_verify
import supp

PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
REASON = "Original file restored from the saved copy; its hash matches the recorded SHA-256."


def sha_of_object(c, key) -> str:
    return hashlib.sha256(c.get_object(Bucket=bucket(), Key=key)["Body"].read()).hexdigest()


def main(sc, browser):
    st = load_state()
    if st.get("tamper_done"):
        raise SystemExit("tamper scene already done once.")
    key, recorded = st["storage_key"], st["sha_v1"]
    assert key.startswith(f"docs/{st['doc_id']}/"), "refusing: key is not this document's own object"
    c = storage_client()
    head = c.head_object(Bucket=bucket(), Key=key)
    orig = c.get_object(Bucket=bucket(), Key=key)["Body"].read()
    assert hashlib.sha256(orig).hexdigest() == recorded, "stored object does not match the recorded hash; not tampering"
    saved = WORK / "original_v1.bin"
    saved.write_bytes(orig)
    saved_sha = hashlib.sha256(saved.read_bytes()).hexdigest()
    restored = False

    p = sc.context(browser, "legal", INSIDE)
    sc.login(p, "legal")
    try:
        with sc.beat(p, "k1", "Save the original V1 bytes locally and compare their hash with the recorded SHA-256"):
            show_supp(p, "Original V1 bytes saved to a local, gitignored work folder",
                      [f"saved copy:      demo_video2/work/original_v1.bin   ({len(orig)} bytes)",
                       f"sha256 of copy:  {saved_sha}",
                       f"recorded sha256: {recorded}   (document_versions.sha256)",
                       "", "copy == recorded  ->  MATCH", "",
                       f"object under test: {key}"],
                      highlight=[saved_sha, "MATCH"])
        with sc.beat(p, "k2", "demo/tamper.py changes ONE byte of this document's own stored object, bypassing the app"):
            out = subprocess.run([PY, str(ROOT / "demo" / "tamper.py"), st["doc_title"]], capture_output=True, text=True,
                                 cwd=str(ROOT), env={**os.environ, "MONGODB_DB": DEMO_DB})
            now = sha_of_object(c, key)
            assert now != recorded, f"tamper did not change the object: {out.stdout} {out.stderr[-300:]}"
            show_supp(p, "Terminal: the attack (direct storage access, not through the application)",
                      [f"$ MONGODB_DB={DEMO_DB} python demo/tamper.py \"{st['doc_title']}\"",
                       *(out.stdout + out.stderr).strip().splitlines()[-2:], "",
                       "Only this document's own object was written. The database row and the blockchain keep the original hash.", "",
                       f"sha256 of the stored object now: {now}", f"recorded sha256 (database + chain):  {recorded}",
                       "-> DIFFERENT"], highlight=["DIFFERENT", now])
        p.goto(f"{APP}/verify/{st['version_id']}")
        p.get_by_role("button", name="Run verification").wait_for()
        with sc.beat(p, "k3", "Run verification: MISMATCH, tamper detected. The recomputed hash differs; stored and on-chain agree"):
            run_verify(p, "MISMATCH")
            p.get_by_text("Recomputed (current file bytes)").first.hover()
        with sc.beat(p, "k4", "The document is flagged TAMPERED: the change is evident; it was not prevented"):
            p.goto(f"{APP}/documents/{st['doc_id']}")
            p.locator("main").get_by_text("TAMPERED", exact=True).first.wait_for()
            p.locator("main").get_by_text("TAMPERED", exact=True).first.hover()
    finally:
        # Always put the original bytes back under the same key (own object only), whatever happened above.
        c.put_object(Bucket=bucket(), Key=key, Body=orig, ContentType=head["ContentType"])
        restored = sha_of_object(c, key) == recorded
        save_state(restored_ok=restored)
        print("restored original bytes, hash matches recorded:", restored)
    assert restored, "RESTORE FAILED - fix the object by hand from demo_video2/work/original_v1.bin"
    with sc.beat(p, "k5", "Restore: the saved bytes are written back to the same key; their hash matches the recorded SHA-256"):
        now = sha_of_object(c, key)
        show_supp(p, "Restore (same storage key, this document's own object)",
                  [f"object key:        {key}", f"sha256 after restore: {now}", f"recorded sha256:      {recorded}", "",
                   "after restore == recorded  ->  MATCH"], highlight=[now, "MATCH"])
    p.goto(f"{APP}/verify/{st['version_id']}")
    p.get_by_role("button", name="Run verification").wait_for()
    with sc.beat(p, "k6", "Run verification again: VERIFIED"):
        run_verify(p, "VERIFIED")
    with sc.beat(p, "k7", "The TAMPERED flag is still on the document: a later pass does not clear it"):
        p.goto(f"{APP}/documents/{st['doc_id']}")
        p.locator("main").get_by_text("TAMPERED", exact=True).first.wait_for()
        p.locator("main").get_by_text("TAMPERED", exact=True).first.hover()
    sc.close_role("legal")

    admin = sc.context(browser, "admin", INSIDE)
    sc.login(admin, "admin")
    admin.goto(f"{APP}/documents/{st['doc_id']}")
    admin.get_by_role("button", name="Clear integrity flag").wait_for()
    with sc.beat(admin, "k8", "Administrator: Clear integrity flag, with a reason of at least 10 characters (audited)"):
        admin.get_by_role("button", name="Clear integrity flag").click()
        admin.get_by_label("Reason for clearing the integrity flag").fill(REASON)
        admin.wait_for_timeout(500)
    with sc.beat(admin, "k9", "Re-verify every anchored version, then clear: the flag is gone"):
        admin.get_by_role("button", name="Re-verify and clear").click()
        admin.get_by_role("button", name="Clear integrity flag").wait_for(state="detached", timeout=90000)
        admin.wait_for_timeout(800)
        admin.locator("main h1").first.hover()
    sc.close_role("admin")
    flag = db().documents.find_one({"title": st["doc_title"]}).get("integrity_flag")
    save_state(tamper_done=True, flag_after=flag)
    print("integrity_flag after clearing:", flag)


run_scene("scene10_tamper", "Scene 10 - Tamper, restore, clear the flag", "s10", main)
