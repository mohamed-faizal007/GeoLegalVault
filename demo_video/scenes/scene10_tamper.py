"""Scene 10: change one byte of the STORED file with demo/tamper.py, verify -> MISMATCH, then restore the original
bytes to the same storage key and verify again. The restore runs even if the scene fails half way."""
import hashlib
import subprocess

from common import *
import supp

PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
PDF = VID / "samples" / "DEMO_Lease_Agreement_v1.pdf"


def verify(p):
    p.get_by_role("button", name="Run verification").click()
    p.get_by_text("3-way hash comparison").wait_for(timeout=60000)
    p.wait_for_timeout(2500)


def main(sc, browser):
    st = load_state()
    orig = PDF.read_bytes()
    assert hashlib.sha256(orig).hexdigest() == st["sha_v1"], "sample PDF no longer matches the stored hash; cannot restore"
    key = st["storage_key"]
    c = supp.storage_client()
    bucket = env("STORAGE_BUCKET")
    p = sc.context(browser, "legal", INSIDE)
    sc.login(p, "legal")
    try:
        sc.say(p, "Someone with direct access to the storage server changes ONE byte of the file (not through the app)")
        out = subprocess.run([PY, str(ROOT / "demo" / "tamper.py"), st["doc_title"]], capture_output=True, text=True, cwd=str(ROOT))
        show_text(p, "Terminal: python demo/tamper.py \"" + st["doc_title"] + "\"",
                  (out.stdout + out.stderr).strip() + "\n\nThis script bypasses the application on purpose. "
                  "The database row and the blockchain still hold the original hash.")
        p.wait_for_timeout(10000)
        p.goto(f"{APP}/verify/{st['version_id']}")
        p.wait_for_timeout(3500)
        sc.say(p, "Run verification again on the same version")
        verify(p)
        sc.say(p, "MISMATCH - tamper detected: the recomputed hash differs from the recorded and on-chain hashes",
               "One changed byte gives a completely different SHA-256 (the avalanche effect). The system makes the change evident; it does not prevent it.")
        p.wait_for_timeout(12000)
        p.screenshot(path=str(sc.dir / "mismatch.png"))
        p.goto(f"{APP}/documents/{st['doc_id']}")
        p.wait_for_timeout(5000)
        sc.say(p, "The document is now flagged with an integrity warning")
        p.wait_for_timeout(5000)
    finally:
        h = c.head_object(Bucket=bucket, Key=key)
        c.put_object(Bucket=bucket, Key=key, Body=orig, ContentType=h["ContentType"])
        restored = hashlib.sha256(c.get_object(Bucket=bucket, Key=key)["Body"].read()).hexdigest() == st["sha_v1"]
        save_state(restored_ok=restored)
        print("restored original bytes:", restored)
    sc.say(p, "Clean-up for the dev data: the original bytes are written back to the same storage key")
    p.goto(f"{APP}/verify/{st['version_id']}")
    p.wait_for_timeout(3000)
    verify(p)
    sc.say(p, "Verify again: VERIFIED. The stored file is the approved file once more",
           "The document keeps its integrity flag until an Administrator clears it (Clear integrity flag).")
    p.wait_for_timeout(10000)
    f = db().documents.find_one({"title": st["doc_title"]}, {"integrity_flag": 1, "status": 1})
    save_state(flag_after=f.get("integrity_flag"), status_after=f.get("status"))
    print("flag after:", f)


run_scene("scene10_tamper", "Scene 10 - Tamper and detect", main)
