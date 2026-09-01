"""Integration tests for anchor_hash / get_onchain_anchor / confirm_tx and
the blockchain module.

Runs against a real, ephemeral local Hardhat node that this test module
spins up itself (per the phase's own testing note: "mock web3, or use a
local hardhat node") — not mocked, so the actual sign -> send -> mine ->
read cycle is genuinely exercised, just against a throwaway local chain
instead of real Sepolia.
"""

import json
import os
import platform
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from bson import ObjectId
from eth_account import Account

from app.core.config import get_settings
from app.modules.blockchain import service as blockchain_service
from app.modules.blockchain.models import AnchorStatus
from app.services import blockchain as chain

_async_test = pytest.mark.asyncio(loop_scope="session")

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts"
ARTIFACT_PATH = (
    CONTRACTS_DIR / "artifacts" / "contracts" / "DocumentAnchor.sol" / "DocumentAnchor.json"
)

# Hardhat's well-known, publicly-documented default dev account #0 (its
# private key is intentionally public — see Hardhat's own docs). Only ever
# used against the throwaway local node this fixture starts, never a real
# network.
_DEV_PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

_ENV_KEYS = ("SEPOLIA_RPC_URL", "SERVICE_WALLET_PRIVATE_KEY", "CONTRACT_ADDRESS", "CHAIN_ID")


_IS_WINDOWS = platform.system() == "Windows"


def _popen_kwargs_for_new_process_group() -> dict[str, Any]:
    """So the whole tree can be killed at once, not just the immediate
    child: `npx` (a wrapper — npx-cli.js on Windows, a shell/node script on
    POSIX) spawns the real `hardhat node` as a SEPARATE child process, and
    a plain proc.terminate()/kill() only ever touches that wrapper. Without
    this, every fixture teardown silently leaked the actual node process —
    confirmed empirically as ~150 accumulated zombie node.exe processes
    across one session's worth of test runs, which is a far more likely
    cause of "times out under load" than the node itself being slow.
    """
    if _IS_WINDOWS:
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _kill_process_tree(proc: subprocess.Popen) -> None:
    if _IS_WINDOWS:
        # taskkill /T walks the real Windows parent->child process tree —
        # this is what actually reaches the grandchild `node.exe` that
        # proc.terminate() alone cannot see.
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    import signal

    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_rpc(url: str, proc: subprocess.Popen, log_file, timeout: float = 90.0) -> None:
    """Poll until the node answers eth_blockNumber, or fail fast the moment
    the process itself has already died (e.g. EADDRINUSE) instead of
    burning the full timeout waiting for a node that will never answer.

    90s (not 30s) because a cold `npx hardhat node` start is genuinely slow
    under load — a busy CI runner or a first-ever compile — and this was
    the single biggest source of spurious failures in this suite.
    """
    deadline = time.time() + timeout
    payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
    while time.time() < deadline:
        exit_code = proc.poll()
        if exit_code is not None:
            log_file.seek(0)
            output = log_file.read()
            raise RuntimeError(
                f"hardhat node process exited early (code {exit_code}) before answering "
                f"RPC at {url}. Output:\n{output}"
            )
        try:
            if httpx.post(url, json=payload, timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"hardhat node at {url} did not become ready within {timeout}s")


def _deploy_contract(rpc_url: str) -> tuple[str, int]:
    from web3 import Web3

    artifact = json.loads(ARTIFACT_PATH.read_text())
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    account = Account.from_key(_DEV_PRIVATE_KEY)
    chain_id = w3.eth.chain_id

    tx: dict[str, Any] = {
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": chain_id,
        "gasPrice": w3.eth.gas_price,
        "data": artifact["bytecode"],
    }
    tx["gas"] = w3.eth.estimate_gas(tx)
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt["contractAddress"], chain_id


@pytest.fixture(scope="session")
def local_chain():
    """One ephemeral Hardhat node for the whole test session (not
    per-module): every test file that needs a chain imports this same
    fixture, and spawning the subprocess only once — instead of once per
    file — was the other big source of flakiness (each spawn is a fresh
    chance to lose a port race or hit a slow cold start). Isolation between
    tests doesn't suffer: every test anchors a freshly-generated ObjectId,
    so collisions across tests are not a real concern.
    """
    if not ARTIFACT_PATH.exists():
        pytest.skip("contracts not compiled — run `cd contracts && npx hardhat compile` first")

    npx = shutil.which("npx")
    if npx is None:
        pytest.skip("npx not on PATH — cannot start a local Hardhat node")

    port = _free_port()
    rpc_url = f"http://127.0.0.1:{port}"
    # Hardhat logs every RPC call to stdout, and this session-scoped node
    # serves every integration test file — a plain PIPE would fill its OS
    # buffer and deadlock the node the moment nothing drains it. A real
    # file never blocks the writer, and still gives us the log for
    # diagnostics if the process dies early.
    log_file = tempfile.TemporaryFile(mode="w+")
    proc = subprocess.Popen(
        [npx, "hardhat", "node", "--hostname", "127.0.0.1", "--port", str(port)],
        cwd=CONTRACTS_DIR,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        **_popen_kwargs_for_new_process_group(),
    )

    original_env = {key: os.environ.get(key) for key in _ENV_KEYS}
    try:
        _wait_for_rpc(rpc_url, proc, log_file)
        contract_address, chain_id = _deploy_contract(rpc_url)

        os.environ["SEPOLIA_RPC_URL"] = rpc_url
        os.environ["SERVICE_WALLET_PRIVATE_KEY"] = _DEV_PRIVATE_KEY
        os.environ["CONTRACT_ADDRESS"] = contract_address
        os.environ["CHAIN_ID"] = str(chain_id)
        get_settings.cache_clear()
        chain._w3 = None

        yield {"rpc_url": rpc_url, "contract_address": contract_address}
    finally:
        _kill_process_tree(proc)
        log_file.close()

        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
        chain._w3 = None


@_async_test
async def test_anchor_hash_records_pending_and_onchain_read_matches(db, local_chain):
    document_id = ObjectId()
    version_id = ObjectId()
    sha256 = "ab" * 32  # a plausible-looking 32-byte hex digest
    version_no = 1
    event_type = 1

    anchor_doc = await blockchain_service.anchor_document_version(
        db,
        document_id=document_id,
        version_id=version_id,
        version_no=version_no,
        sha256=sha256,
        event_type=event_type,
    )

    assert anchor_doc["status"] == AnchorStatus.PENDING.value
    assert anchor_doc["tx_hash"] is not None
    assert anchor_doc["tx_hash"].startswith("0x")
    assert anchor_doc["contract_address"] == local_chain["contract_address"]

    stored = await blockchain_service.get_latest_anchor_for_version(db, str(version_id))
    assert stored is not None
    assert stored["_id"] == anchor_doc["_id"]

    onchain = await chain.get_onchain_anchor(str(document_id), version_no)
    assert onchain["exists"] is True
    assert onchain["hash"] == "0x" + sha256
    assert onchain["event_type"] == event_type


@_async_test
async def test_confirm_tx_reports_success_once_mined(db, local_chain):
    document_id = ObjectId()
    tx_hash = await chain.anchor_hash(str(document_id), 1, "cd" * 32, 2)

    receipt = await chain.confirm_tx(tx_hash)
    assert receipt is not None
    assert receipt["status"] == 1
    assert receipt["block_number"] > 0


@_async_test
async def test_reanchor_same_document_version_fails_and_records_failed(db, local_chain):
    document_id = ObjectId()
    version_id = ObjectId()
    sha256 = "11" * 32

    first = await blockchain_service.anchor_document_version(
        db,
        document_id=document_id,
        version_id=version_id,
        version_no=1,
        sha256=sha256,
        event_type=1,
    )
    assert first["status"] == AnchorStatus.PENDING.value

    second = await blockchain_service.anchor_document_version(
        db,
        document_id=document_id,
        version_id=ObjectId(),
        version_no=1,  # same document_id + version_no as `first`
        sha256=sha256,
        event_type=1,
    )
    assert second["status"] == AnchorStatus.FAILED.value
    assert second["tx_hash"] is None
    assert "already anchored" in second["error"]


@_async_test
async def test_get_onchain_anchor_reports_not_exists_for_unanchored_version(local_chain):
    result = await chain.get_onchain_anchor("never-anchored-doc", 999)
    assert result["exists"] is False


def test_sha256_hex_to_bytes32_round_trips():
    sha256_hex = "ab" * 32
    raw = chain.sha256_hex_to_bytes32(sha256_hex)
    assert len(raw) == 32
    assert raw.hex() == sha256_hex


@_async_test
async def test_anchor_api_returns_stored_anchor_with_etherscan_link(client, db, local_chain):
    from app.modules.geofences.schemas import GeofenceCreate, GeoJSONPolygon
    from app.modules.geofences.service import create_geofence
    from app.modules.users.models import Role
    from app.modules.users.schemas import UserCreate
    from app.modules.users.service import create_user
    from app.modules.versions import service as versions_service

    hq_ring = [
        [78.14, 11.66],
        [78.16, 11.66],
        [78.16, 11.68],
        [78.14, 11.68],
        [78.14, 11.66],
    ]
    fence = await create_geofence(
        db, GeofenceCreate(name="HQ", region=GeoJSONPolygon(coordinates=[hq_ring]))
    )
    await create_user(
        db,
        UserCreate(
            email="viewer@example.com",
            password="Str0ngPassw0rd!",
            name="Viewer",
            role=Role.AUDITOR,
            assigned_geofence_ids=[fence.id],
        ),
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@example.com", "password": "Str0ngPassw0rd!"},
    )
    token = login.json()["access_token"]

    document_id = ObjectId()
    version_doc = await versions_service.insert_version(
        db,
        document_id=document_id,
        version_no=1,
        sha256="ef" * 32,
        prev_version_hash=None,
        storage_key=f"docs/{document_id}/v1",
        size_bytes=10,
        mime="application/pdf",
        uploaded_by=ObjectId(),
    )
    anchor_doc = await blockchain_service.anchor_document_version(
        db,
        document_id=document_id,
        version_id=version_doc["_id"],
        version_no=1,
        sha256="ef" * 32,
        event_type=1,
    )

    response = await client.get(
        f"/api/v1/blockchain/anchor/{version_doc['_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["tx_hash"] == anchor_doc["tx_hash"]
    assert body["etherscan_url"] == f"https://sepolia.etherscan.io/tx/{anchor_doc['tx_hash']}"
    assert body["onchain"]["exists"] is True
    assert body["onchain"]["hash"] == "0x" + "ef" * 32
