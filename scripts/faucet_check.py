"""Sepolia faucet balance check — implemented in Phase 5.

Reuses the same web3.py provider config and service wallet as
app/services/blockchain.py (Guardrail #2: no key ever printed here, only the
derived address). Prints the service wallet's Sepolia ETH balance and warns
if it's too low to cover anchoring gas.

Usage (run from repo root):
    python scripts/faucet_check.py
    python scripts/faucet_check.py --min-eth 0.02
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from web3 import Web3  # noqa: E402

from app.services.blockchain import BlockchainNotConfigured, get_service_account, get_web3  # noqa: E402

DEFAULT_MIN_ETH = 0.01


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the service wallet's Sepolia ETH balance.")
    parser.add_argument(
        "--min-eth",
        type=float,
        default=DEFAULT_MIN_ETH,
        help=f"Warn if the balance is below this many ETH (default: {DEFAULT_MIN_ETH}).",
    )
    args = parser.parse_args()

    try:
        w3 = get_web3()
        account = get_service_account()
    except BlockchainNotConfigured as exc:
        print(f"Not configured: {exc}")
        sys.exit(1)

    balance_wei = w3.eth.get_balance(account.address)
    balance_eth = Web3.from_wei(balance_wei, "ether")

    print(f"Service wallet: {account.address}")
    print(f"Balance: {balance_eth} ETH")

    if balance_eth < args.min_eth:
        print(
            f"WARNING: balance is below {args.min_eth} ETH — may not be enough for "
            "gas on upcoming anchor transactions. Top up from a Sepolia faucet, e.g. "
            "https://sepoliafaucet.com or https://www.alchemy.com/faucets/ethereum-sepolia."
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
