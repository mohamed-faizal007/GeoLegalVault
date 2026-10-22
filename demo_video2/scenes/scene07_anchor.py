"""Scene 7: what is anchored on Sepolia: the Anchor page (recorded vs live on-chain hash, Match, Sepolia testnet label,
Copy button), what the contract stores, and the public Etherscan page. Read-only; re-runnable."""
from common import *
import supp

ZOOM_ETHERSCAN = r"""
() => {
  const txt = (e) => (e.textContent || '').trim();
  const find = (re) => [...document.querySelectorAll('div,span,td,dt,label,h5')].find(e => re.test(txt(e)) && txt(e).length < 40);
  const st = find(/^Status:?$/i), fee = find(/^Transaction Fee:?$/i);
  const hl = (e) => { if (e && e.parentElement) e.parentElement.style.cssText += ';outline:4px solid #ffd33d;outline-offset:4px;background:rgba(255,211,61,.12)'; };
  hl(st); hl(fee);
  window.__glvRows = [st, fee];
  return [!!st, !!fee];
}
"""


def main(sc, browser):
    st = load_state()
    p = sc.context(browser, "legal", INSIDE)
    sc.login(p, "legal")
    p.goto(f"{APP}/documents/{st['doc_id']}/versions")
    p.locator("main").get_by_text("SHA-256").first.wait_for()

    with sc.beat(p, "k1", "Version History: V1 is ACTIVE and CONFIRMED. Open View on-chain"):
        p.locator("main").get_by_role("link", name="View on-chain").first.click()
        p.get_by_text("Blockchain Anchor Record").wait_for()
        p.wait_for_selector("[data-testid=hash-comparison]")
    sc.zoom(p, 1.05)   # one view: both hashes, Match, label, Copy button
    with sc.beat(p, "k2", "Recorded hash (database) and live on-chain hash side by side: Match"):
        p.locator("[data-testid=hash-comparison]").hover()
    with sc.beat(p, "k3", "Network label Sepolia testnet, contract address, transaction hash with a Copy button"):
        p.get_by_role("button", name="Copy transaction hash").click()
        p.get_by_text("Copied").first.wait_for()

    ap = api("GET", f"/blockchain/anchor/{st['version_id']}", token=token_for(EMAILS["legal"], demo_password()))
    onchain = ap[1].get("onchain")
    with sc.beat(p, "k4", "Supplementary view: what the contract stores per version, and what it does not"):
        show_supp(p, "blockchain_anchors row, and the live read of the DocumentAnchor contract (Sepolia testnet)",
                  supp.anchor_lines(st["doc_id"]) + ["", "contract.getAnchor(documentId, version)  ->  read live by the API:",
                                                     *j(onchain).splitlines(), "",
                                                     "ON-CHAIN per version: hash (bytes32), version (uint32), eventType (uint8), block time (uint64).",
                                                     "NOT on-chain: the PDF, its filename, any person's name.  A second anchor for the same version reverts."],
                  highlight=[st["sha_v1"]], font=26)
    # Load and zoom the (heavy) Etherscan page first, un-narrated, so the beat itself is a static page.
    try:
        p.goto(f"https://sepolia.etherscan.io/tx/{st['tx_v1']}", wait_until="domcontentloaded", timeout=60000)
        p.wait_for_timeout(6000)
        got = p.get_by_text("Got it!")
        if got.count():
            got.first.click()   # dismiss the cookie banner
            p.wait_for_timeout(600)
        found = p.evaluate(ZOOM_ETHERSCAN)
    except Exception as e:  # noqa: BLE001
        found = f"failed: {type(e).__name__}"
    print("etherscan zoom (status row, fee row):", found)
    sc.dim(p, True)   # dim the bright page (an overlay under the caption bar)
    p.wait_for_timeout(800)
    with sc.beat(p, "k5", "Public Etherscan page for the Sepolia testnet transaction: Status Success and the fee"):
        p.screenshot(path=str(sc.dir / "etherscan.png"))
        p.mouse.move(900, 500)
    with sc.beat(p, "k6", "One service wallet signs every anchor; one SHA-256 per file, no Merkle tree"):
        p.goto(f"{APP}/versions/{st['version_id']}/blockchain")
        p.wait_for_selector("[data-testid=hash-comparison]")
        sc.zoom(p, 1.05)
        p.get_by_text("Contract address").first.hover()
    sc.close_role("legal")


run_scene("scene07_anchor", "Scene 7 - Anchored on Sepolia (testnet)", "s07", main)
