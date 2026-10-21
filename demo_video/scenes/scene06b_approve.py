"""Scene 6b: the Legal Officer approves inside the zone. ONE real Sepolia transaction (testnet). Do not re-run."""
import subprocess
import time

from common import *

PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")


def balance() -> str:
    out = subprocess.run([PY, str(ROOT / "scripts" / "faucet_check.py")], capture_output=True, text=True, cwd=str(ROOT)).stdout
    return [l for l in out.splitlines() if l.startswith("Balance")][0].split(":", 1)[1].strip()


def main(sc, browser):
    st = load_state()
    if st.get("approved_at"):
        raise SystemExit("Already approved once; refusing to send a second transaction.")
    before = balance()
    save_state(balance_before=before)
    p = sc.context(browser, "legal", INSIDE)
    sc.say(p, "Legal Officer signs in (not the uploader, not the reviewer)", geo=True)
    sc.login(p, "legal")
    p.goto(f"{APP}/documents/{st['doc_id']}")
    p.wait_for_timeout(3500)
    sc.say(p, "Document is PENDING_APPROVAL. The Approve button is shown because this user did not upload it", geo=True)
    p.wait_for_timeout(4000)
    sc.say(p, "Click Approve (location is checked by the server first). Approval starts the anchoring automatically", "There is no anchor button: the backend's own service wallet signs, never the user. Ethereum SEPOLIA TESTNET.", geo=True)
    p.get_by_role("button", name="Approve", exact=True).click()
    save_state(approved_at=time.time())
    sc.say(p, "Waiting for the Sepolia testnet to include the transaction (about 12 s per block; trimmed in editing)")
    p.get_by_text("ACTIVE", exact=True).first.wait_for(timeout=180000)
    p.wait_for_timeout(3000)
    sc.say(p, "Status ACTIVE: the anchor was confirmed on the Sepolia testnet")
    p.wait_for_timeout(5000)
    after = balance()
    save_state(balance_after=after)
    print("balance before:", before, "after:", after)


run_scene("scene06b_approve", "Scene 6 - Approval inside the zone", main)
