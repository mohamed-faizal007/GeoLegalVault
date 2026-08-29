"""Throwaway smoke test for the Phase 5 anchor service — not a permanent
deliverable, safe to delete once you've confirmed it works.

Sends one real anchor tx to whatever chain SEPOLIA_RPC_URL points at
(intended: Sepolia, once you've set SEPOLIA_RPC_URL, SERVICE_WALLET_PRIVATE_KEY,
and CONTRACT_ADDRESS in .env to real values and deployed the contract),
waits for it to confirm, then reads it back on-chain.

Usage (run from repo root):
    python scripts/anchor_smoke_test.py [document_id]

document_id defaults to a fresh random value each run, since the contract
permanently reverts on re-anchoring the same (documentId, version) pair.
"""

import asyncio
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.services import blockchain as chain  # noqa: E402

VERSION = 1
EVENT_TYPE = 1  # placeholder — no eventType vocabulary is fixed until Phase 6
DUMMY_SHA256 = "ab" * 32  # a plausible-looking (but fake) 32-byte hex digest
CONFIRM_TIMEOUT_SEC = 300
POLL_INTERVAL_SEC = 5


async def main() -> None:
    document_id = sys.argv[1] if len(sys.argv) > 1 else f"smoke-test-{uuid.uuid4().hex[:8]}"

    print(
        f"Anchoring document_id={document_id!r} version={VERSION} "
        f"sha256={DUMMY_SHA256} event_type={EVENT_TYPE} ..."
    )
    tx_hash = await chain.anchor_hash(document_id, VERSION, DUMMY_SHA256, EVENT_TYPE)
    print(f"Sent. tx_hash = {tx_hash}")
    print(f"Etherscan: https://sepolia.etherscan.io/tx/{tx_hash}")

    print(f"Waiting for confirmation (up to {CONFIRM_TIMEOUT_SEC}s)...")
    deadline = time.monotonic() + CONFIRM_TIMEOUT_SEC
    receipt = None
    while time.monotonic() < deadline:
        receipt = await chain.confirm_tx(tx_hash)
        if receipt is not None:
            break
        await asyncio.sleep(POLL_INTERVAL_SEC)

    if receipt is None:
        print("Timed out waiting for confirmation — check the Etherscan link above.")
        return

    print(f"Confirmed in block {receipt['block_number']} (status={receipt['status']}).")

    onchain = await chain.get_onchain_anchor(document_id, VERSION)
    print("On-chain read-back:", onchain)

    assert onchain["exists"], "anchor not found on-chain after confirmation!"
    assert onchain["hash"] == f"0x{DUMMY_SHA256}", "on-chain hash does not match what we sent!"
    print("OK: on-chain hash matches what was sent.")


if __name__ == "__main__":
    asyncio.run(main())
