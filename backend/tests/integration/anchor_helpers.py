"""Shared helpers for the REL-01 reliability tests (D-037..D-042).

- `fast_anchor` shrinks every retry/lease/timeout setting to milliseconds so the
  real backoff logic runs for real, just quickly.
- `hard_timeout` bounds a whole test body. There is no pytest-timeout in this repo,
  so a hung node, lease or subprocess fails the test instead of the CI job.
- `ChainNode` is a Hardhat node the *test* controls (kill, restart, manual mining),
  unlike the session-wide `local_chain` fixture which must never go down.
"""

import asyncio
import functools
import json
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest

from app.core.config import get_settings
from app.services import blockchain as chain
from tests.integration.test_anchor import (
    _DEV_PRIVATE_KEY,
    _ENV_KEYS,
    CONTRACTS_DIR,
    _deploy_contract,
    _free_port,
    _kill_process_tree,
    _popen_kwargs_for_new_process_group,
    _start_timeout_sec,
    _wait_for_rpc,
)

# Hardhat's public default account #1: funded on the local node but NOT a writer on
# a contract deployed by account #0, so it is how we get a genuine NOT_AUTHORIZED.
NON_WRITER_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"

FAST_SETTINGS = {
    # approve()'s own in-request attempts: one, quick.
    "ANCHOR_MAX_ATTEMPTS": "1",
    "ANCHOR_RETRY_BACKOFF_SEC": "0.01",
    "ANCHOR_CONFIRM_POLL_ATTEMPTS": "3",
    "ANCHOR_CONFIRM_POLL_INTERVAL_SEC": "0.1",
    # the worker's policy (D-038), in milliseconds
    "ANCHOR_RETRY_BASE_SEC": "0.05",
    "ANCHOR_RETRY_CAP_SEC": "0.2",
    "ANCHOR_RETRY_MAX_ATTEMPTS": "5",
    "ANCHOR_REVERT_MAX_ATTEMPTS": "2",
    "ANCHOR_FUNDS_RETRY_BASE_SEC": "0.05",
    "ANCHOR_FUNDS_RETRY_CAP_SEC": "0.2",
    "ANCHOR_PENDING_TIMEOUT_SEC": "1.5",
    "ANCHOR_LEASE_SEC": "30",  # must stay longer than ANCHOR_PENDING_TIMEOUT_SEC (D-038)
}

FAKE_SECRET = "SECRETKEYABCDEF123456"
LEAKY_RPC_ERROR = (
    "HTTPSConnectionPool(host='eth-sepolia.g.alchemy.com', port=443): Max retries exceeded "
    f"with url: /v2/{FAKE_SECRET} (Caused by NewConnectionError('connection refused'))"
)


@pytest.fixture
def fast_anchor():
    saved = {key: os.environ.get(key) for key in FAST_SETTINGS}
    os.environ.update(FAST_SETTINGS)
    get_settings.cache_clear()
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def hard_timeout(seconds: float):
    """Fail the test (instead of hanging) if its whole body runs longer than `seconds`."""

    def decorator(fn: Callable[..., Awaitable[Any]]):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(fn(*args, **kwargs), timeout=seconds)
            except TimeoutError:
                pytest.fail(f"{fn.__name__} exceeded its {seconds}s hard timeout")

        return wrapper

    return decorator


async def run_pass(db) -> Any:
    from app.workers import anchor_confirmer as worker

    return await worker.run_pass(db)


async def drive(db, done: Callable[[], Awaitable[bool]], *, timeout: float = 25.0) -> None:
    """Run worker passes until `done()` is true, or fail with a clear message."""
    deadline = time.monotonic() + timeout
    while True:
        await run_pass(db)
        if await done():
            return
        if time.monotonic() > deadline:
            raise AssertionError(f"condition not reached within {timeout}s of worker passes")
        await asyncio.sleep(0.05)


def naive(dt):
    """Mongo hands datetimes back naive-UTC; make comparisons explicit."""
    return dt.replace(tzinfo=None) if dt is not None and dt.tzinfo else dt


class ChainNode:
    """A Hardhat node on one fixed port that a test can kill, restart and put in
    manual-mining mode. A restart wipes the chain (this is what a dropped tx / testnet
    reset looks like) and redeploys the contract; account #0's nonce restarts at 0, so
    the contract address is identical and the app's CONTRACT_ADDRESS stays valid."""

    def __init__(self) -> None:
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.address: str | None = None
        self.chain_id: int | None = None
        self._proc: subprocess.Popen | None = None
        self._log = None

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        npx = shutil.which("npx")
        if npx is None:
            pytest.skip("npx not on PATH — cannot start a local Hardhat node")
        last_error: Exception | None = None
        for _ in range(3):  # the port can linger for a moment after a kill
            self._log = tempfile.TemporaryFile(mode="w+")
            self._proc = subprocess.Popen(
                [npx, "hardhat", "node", "--hostname", "127.0.0.1", "--port", str(self.port)],
                cwd=CONTRACTS_DIR,
                stdout=self._log,
                stderr=subprocess.STDOUT,
                **_popen_kwargs_for_new_process_group(),
            )
            try:
                _wait_for_rpc(self.url, self._proc, self._log, timeout=_start_timeout_sec())
                break
            except RuntimeError as exc:
                last_error = exc
                _kill_process_tree(self._proc)
                self._log.close()
                time.sleep(1)
        else:
            raise RuntimeError(f"hardhat node would not start: {last_error}")

        address, chain_id = _deploy_contract(self.url)
        assert self.address in (None, address), "redeploy changed the contract address"
        self.address, self.chain_id = address, chain_id

    def kill(self) -> None:
        if self._proc is not None:
            _kill_process_tree(self._proc)
            self._proc.wait(timeout=20)
        if self._log is not None:
            self._log.close()
            self._log = None

    def restart(self) -> None:
        self.kill()
        self.start()

    def ensure_up(self) -> None:
        if not self.running:
            self.start()
        self.automine(True)

    def _rpc(self, method: str, params: list[Any]) -> Any:
        response = httpx.post(
            self.url,
            json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
            timeout=10,
        )
        body = response.json()
        assert "error" not in body, body
        return body["result"]

    def automine(self, on: bool) -> None:
        self._rpc("evm_setAutomine", [on])

    def mine(self) -> None:
        self._rpc("evm_mine", [])


def configure_app_for(
    node: ChainNode, *, wallet_key: str = _DEV_PRIVATE_KEY
) -> dict[str, str | None]:
    """Point the app's chain settings at `node`; returns what to restore."""
    original = {key: os.environ.get(key) for key in _ENV_KEYS}
    os.environ["SEPOLIA_RPC_URL"] = node.url
    os.environ["SERVICE_WALLET_PRIVATE_KEY"] = wallet_key
    os.environ["CONTRACT_ADDRESS"] = node.address or ""
    os.environ["CHAIN_ID"] = str(node.chain_id)
    get_settings.cache_clear()
    chain._w3 = None
    return original


def restore_app_env(original: dict[str, str | None]) -> None:
    for key, value in original.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()
    chain._w3 = None


def use_wallet(key: str) -> None:
    os.environ["SERVICE_WALLET_PRIVATE_KEY"] = key
    get_settings.cache_clear()


def wallet_nonce() -> int:
    """Pending tx count of the service wallet: rises by one per tx actually sent."""
    address = chain.get_service_account().address
    return chain.get_web3().eth.get_transaction_count(address, "pending")


async def anchor_rows(db, document_id) -> list[dict]:
    from bson import ObjectId

    oid = document_id if isinstance(document_id, ObjectId) else ObjectId(document_id)
    cursor = db["blockchain_anchors"].find({"document_id": oid}).sort("created_at", 1)
    return await cursor.to_list(None)


def everything_as_text(*parts: Any) -> str:
    return json.dumps(parts, default=str)
