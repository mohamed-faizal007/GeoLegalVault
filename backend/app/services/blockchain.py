"""On-chain anchoring via web3.py against the DocumentAnchor contract
(Plan Parts 12, 18).

Guardrails: #1 (only hash + small metadata ever go on-chain), #2 (the
service-wallet key lives only in env, never logged), #3 (this one backend
service wallet signs every anchor — there is no per-user MetaMask path and
no user-triggered anchoring endpoint anywhere in this codebase).

Nonce handling: sends are serialized with an asyncio.Lock so two concurrent
anchor attempts from this process never race for the same nonce (Part 12:
"Nonce collision -> serialize anchoring").
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import requests
from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import BadFunctionCallOutput, TransactionNotFound
from web3.types import TxParams

from app.core.config import get_settings

_ABI_PATH = Path(__file__).parent / "document_anchor_abi.json"
_ABI: list[dict[str, Any]] = json.loads(_ABI_PATH.read_text())

_send_lock = asyncio.Lock()
_w3: Web3 | None = None


class BlockchainNotConfigured(Exception):
    """SEPOLIA_RPC_URL / SERVICE_WALLET_PRIVATE_KEY / CONTRACT_ADDRESS are
    still placeholders — expected until the manual deploy step is done."""


class ChainReadTimeout(TimeoutError):
    """An on-chain read did not finish within CHAIN_READ_TIMEOUT_SEC (D-049)."""


class ContractNotDeployed(Exception):
    """The node answered, but there is no contract code at CONTRACT_ADDRESS (a reset or
    redeployed chain). Definitive: an anchor cannot exist there (D-049)."""


def _is_placeholder(value: str) -> bool:
    return not value or "CHANGE_ME" in value.upper()


def _normalize_key(value: str) -> str:
    return value if value.startswith("0x") else f"0x{value}"


def get_web3() -> Web3:
    global _w3
    if _w3 is None:
        settings = get_settings()
        if _is_placeholder(settings.SEPOLIA_RPC_URL):
            raise BlockchainNotConfigured("SEPOLIA_RPC_URL is not configured")
        _w3 = Web3(Web3.HTTPProvider(settings.SEPOLIA_RPC_URL))
    return _w3


def get_service_account() -> LocalAccount:
    settings = get_settings()
    if _is_placeholder(settings.SERVICE_WALLET_PRIVATE_KEY):
        raise BlockchainNotConfigured("SERVICE_WALLET_PRIVATE_KEY is not configured")
    return Account.from_key(_normalize_key(settings.SERVICE_WALLET_PRIVATE_KEY))


def get_contract() -> Contract:
    settings = get_settings()
    if _is_placeholder(settings.CONTRACT_ADDRESS):
        raise BlockchainNotConfigured("CONTRACT_ADDRESS is not configured")
    address = Web3.to_checksum_address(settings.CONTRACT_ADDRESS)
    return get_web3().eth.contract(address=address, abi=_ABI)


def sha256_hex_to_bytes32(sha256_hex: str) -> bytes:
    """A SHA-256 hex digest is exactly 32 bytes — decodes straight into
    Solidity's bytes32, no hashing-of-a-hash involved."""
    return bytes.fromhex(sha256_hex)


async def anchor_hash(document_id: str, version: int, sha256_hex: str, event_type: int) -> str:
    """Builds, signs (service wallet), and sends the anchor tx. Returns the
    0x-prefixed tx hash. Raises BlockchainNotConfigured or the underlying
    web3/RPC exception on failure — callers are responsible for catching
    these and recording PENDING/FAILED without crashing the request (Part
    12's failure-handling table)."""
    w3 = get_web3()
    account = get_service_account()
    contract = get_contract()
    hash_bytes = sha256_hex_to_bytes32(sha256_hex)
    fn = contract.functions.anchor(document_id, version, hash_bytes, event_type)

    async with _send_lock:
        nonce = await asyncio.to_thread(w3.eth.get_transaction_count, account.address, "pending")
        gas_estimate = await asyncio.to_thread(fn.estimate_gas, {"from": account.address})
        tx: TxParams = fn.build_transaction(
            {
                "from": account.address,
                "nonce": nonce,
                "gas": int(gas_estimate * 1.2),  # headroom over the estimate
                "chainId": get_settings().CHAIN_ID,
            }
        )
        signed = account.sign_transaction(tx)
        tx_hash = await asyncio.to_thread(w3.eth.send_raw_transaction, signed.raw_transaction)

    return "0x" + tx_hash.hex().removeprefix("0x")


def _read_contract(timeout: float) -> tuple[Web3, Contract]:
    """A read-only Web3 + contract with a bounded HTTP timeout and no retries (web3 7's
    default is 30 s x 5 on eth_call). Separate from the shared signing client on purpose:
    the send path is not changed by the read bound (D-049). Built per call; cheap."""
    settings = get_settings()
    if _is_placeholder(settings.CONTRACT_ADDRESS):
        raise BlockchainNotConfigured("CONTRACT_ADDRESS is not configured")
    if _is_placeholder(settings.SEPOLIA_RPC_URL):
        raise BlockchainNotConfigured("SEPOLIA_RPC_URL is not configured")
    w3 = Web3(
        Web3.HTTPProvider(
            settings.SEPOLIA_RPC_URL,
            request_kwargs={"timeout": timeout},
            exception_retry_configuration=None,
        )
    )
    address = Web3.to_checksum_address(settings.CONTRACT_ADDRESS)
    return w3, w3.eth.contract(address=address, abi=_ABI)


async def get_onchain_anchor(document_id: str, version: int) -> dict[str, Any]:
    """Reads the contract's mapping directly — the ground truth used by the
    3-way verification loop (Phase 7), independent of whatever this app's
    own database says.

    Bounded by CHAIN_READ_TIMEOUT_SEC. Raises ChainReadTimeout (stuck node),
    ContractNotDeployed (the node has no code at the address: definitive), or the
    underlying error (unreachable, undecodable reply). Callers must treat an exception as
    "could not read", never as "not anchored" (D-049)."""
    timeout = get_settings().CHAIN_READ_TIMEOUT_SEC
    w3, contract = _read_contract(timeout)

    def _read() -> tuple[bytes, int, int, bool]:
        try:
            return contract.functions.getAnchor(document_id, version).call()
        except BadFunctionCallOutput:
            # An empty/undecodable reply is "no answer" unless the address holds no code at
            # all, which is a definitive "no anchor can be here".
            if not w3.eth.get_code(contract.address):
                raise ContractNotDeployed("no contract code at CONTRACT_ADDRESS") from None
            raise

    try:
        # The deadline is a backstop: the HTTP timeout normally fires first. It does not
        # cover a thread that is still running; that one ends on its own HTTP timeout.
        hash_bytes, event_type, ts, exists = await asyncio.wait_for(
            asyncio.to_thread(_read), timeout=timeout + 1.0
        )
    except (TimeoutError, requests.exceptions.Timeout):
        raise ChainReadTimeout("on-chain read timed out") from None
    return {
        "hash": "0x" + hash_bytes.hex().removeprefix("0x"),
        "event_type": event_type,
        "ts": ts,
        "exists": exists,
    }


async def tx_known(tx_hash: str) -> bool:
    """True if the node still knows this tx (mined or in its mempool). False only when
    the node answers "not found"; an unreachable node raises, so "can't tell" is never
    read as "dropped" (D-038 addendum)."""
    w3 = get_web3()
    try:
        await asyncio.to_thread(w3.eth.get_transaction, tx_hash)
    except TransactionNotFound:
        return False
    return True


async def confirm_tx(tx_hash: str) -> dict[str, Any] | None:
    """None while still pending or not yet mined to ANCHOR_CONFIRMATIONS
    depth; otherwise {"block_number", "status"} (status: 1 success, 0
    reverted)."""
    w3 = get_web3()
    settings = get_settings()
    try:
        receipt = await asyncio.to_thread(w3.eth.get_transaction_receipt, tx_hash)
    except TransactionNotFound:
        return None

    latest_block = await asyncio.to_thread(lambda: w3.eth.block_number)
    confirmations = latest_block - receipt["blockNumber"] + 1
    if confirmations < settings.ANCHOR_CONFIRMATIONS:
        return None

    return {"block_number": receipt["blockNumber"], "status": receipt["status"]}
