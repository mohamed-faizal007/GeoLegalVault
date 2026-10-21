"""Scene 7: the anchor on Sepolia: what is stored, tx hash, Etherscan, live on-chain read. Read-only; re-runnable."""
from common import *
import supp


def main(sc, browser):
    st = load_state()
    p = sc.context(browser, "legal", INSIDE)
    sc.say(p, "Legal Officer opens Version History", "Document status is ACTIVE.")
    sc.login(p, "legal")
    p.goto(f"{APP}/documents/{st['doc_id']}/versions")
    p.wait_for_timeout(4000)
    sc.say(p, "Version 1 is ACTIVE and anchored. Click View on-chain")
    p.get_by_role("link", name="View on-chain").or_(p.get_by_role("button", name="View on-chain")).first.click()
    p.wait_for_timeout(4000)
    sc.say(p, "Blockchain Anchor Record: network sepolia (a TEST network), contract address, transaction hash, block number")
    p.wait_for_timeout(8000)
    p.mouse.wheel(0, 600)
    sc.say(p, "Live on-chain read: the app asks the contract now. Hash on-chain equals the recorded hash")
    p.wait_for_timeout(9000)
    body = p.inner_text("body")
    import re
    m = re.search(r"0x[0-9a-fA-F]{64}", body)
    if m:
        save_state(tx_hash=m.group(0))
    sc.say(p, "Supplementary view: what is stored on-chain, and what is not")
    show_text(p, "blockchain_anchors record, and the contract's on-chain record",
              supp.anchor_view(st["doc_id"]) +
              "\n\nOn-chain (DocumentAnchor.sol), keyed by keccak256(documentId, version):\n"
              "  hash (bytes32) | version (uint32) | eventType (uint8, 1 = APPROVED) | ts (uint64 block time) | exists\n"
              "NOT on-chain: the PDF, its filename, any person's name. A second anchor for the same document and version reverts ('already anchored').")
    p.wait_for_timeout(16000)

    tx = load_state().get("tx_hash")
    if tx:
        sc.say(p, "Public Etherscan page for this transaction (Sepolia testnet explorer)")
        try:
            p.goto(f"https://sepolia.etherscan.io/tx/{tx}", wait_until="domcontentloaded", timeout=45000)
            p.wait_for_timeout(9000)
            p.screenshot(path=str(sc.dir / "etherscan.png"))
        except Exception as e:  # noqa: BLE001
            print("etherscan load failed:", type(e).__name__)


run_scene("scene07_anchor", "Scene 7 - Anchored on Sepolia (testnet)", main)
