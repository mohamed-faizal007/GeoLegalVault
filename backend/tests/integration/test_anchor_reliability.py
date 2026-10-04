"""REL-01 reliability tests (D-037..D-042): a document must not be left stuck in
APPROVED because an anchor failed, was dropped, or the worker died.

Everything here runs against the real local Hardhat node (never Sepolia), real
Mongo and real RustFS. The two node-lifecycle tests really kill and restart the
node process. Every test body has a hard timeout.
"""

import asyncio
import hashlib
import logging
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

from app.core.config import get_settings
from app.services import blockchain as chain
from app.services import storage
from tests.integration.anchor_helpers import (
    FAKE_SECRET,
    LEAKY_RPC_ERROR,
    NON_WRITER_KEY,
    ChainNode,
    anchor_rows,
    configure_app_for,
    drive,
    everything_as_text,
    fast_anchor,  # noqa: F401 (fixture)
    hard_timeout,
    naive,
    restore_app_env,
    run_pass,
    use_wallet,
    wallet_nonce,
)
from tests.integration.test_anchor import _DEV_PRIVATE_KEY
from tests.integration.test_concurrency import _pending_approval
from tests.integration.test_workflow import PDF_BYTES, _auth, _geo

pytestmark = pytest.mark.asyncio(loop_scope="session")

BACKEND_DIR = Path(__file__).resolve().parents[2]
PDF_SHA = hashlib.sha256(PDF_BYTES).hexdigest()


# --- fixtures ----------------------------------------------------------------


@pytest.fixture(scope="module")
def _node():
    node = ChainNode()
    node.start()
    original = configure_app_for(node)
    try:
        yield node
    finally:
        node.kill()
        restore_app_env(original)


@pytest.fixture
def node(_node):
    """The module's node, guaranteed up, auto-mining, and with the writer wallet."""
    _node.ensure_up()
    use_wallet(_DEV_PRIVATE_KEY)
    chain._w3 = None
    return _node


# --- small helpers -----------------------------------------------------------


async def _approve(client, ctx) -> dict:
    response = await client.post(
        f"/api/v1/documents/{ctx['document_id']}/approve",
        headers={**_auth(ctx["approvers"][0]), **_geo()},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _doc(db, ctx) -> dict:
    return await db["documents"].find_one({"_id": ObjectId(ctx["document_id"])})


async def _is_active(db, ctx) -> bool:
    return (await _doc(db, ctx))["status"] == "ACTIVE"


async def _is_permanent(db, ctx) -> bool:
    return bool(((await _doc(db, ctx)).get("anchor_retry") or {}).get("permanent"))


async def _approve_with_failing_send(client, ctx, error: Exception | None = None) -> dict:
    """approve() while every send fails: leaves the document APPROVED with a FAILED row,
    exactly the state REL-01 is about, without needing to take the node down."""
    failing = AsyncMock(side_effect=error or ConnectionError(LEAKY_RPC_ERROR))
    with patch.object(chain, "anchor_hash", new=failing):
        return await _approve(client, ctx)


async def _assert_anchored_exactly_once(db, ctx) -> None:
    rows = await anchor_rows(db, ctx["document_id"])
    confirmed = [r for r in rows if r["status"] == "CONFIRMED"]
    in_flight = [r for r in rows if r["status"] == "PENDING"]
    assert len(confirmed) == 1, [(r["status"], r.get("error")) for r in rows]
    assert not in_flight
    onchain = await chain.get_onchain_anchor(ctx["document_id"], 1)
    assert onchain["exists"] is True and onchain["hash"] == "0x" + PDF_SHA
    version = await db["document_versions"].find_one({"_id": ObjectId(ctx["version_id"])})
    assert version["status"] == "ACTIVE" and version["anchored"] is True
    assert (await _doc(db, ctx))["anchor_pending_alert"] is False


# --- 1. the node is killed and restarted ---------------------------------------


@hard_timeout(240)
async def test_node_down_then_restarted_worker_survives_and_anchors(
    client, db, node, fast_anchor  # noqa: F811
):
    ctx = await _pending_approval(client, db)
    node.kill()

    body = await _approve(client, ctx)
    assert body["anchor_status"] == "FAILED"
    document = await _doc(db, ctx)
    assert document["status"] == "APPROVED" and document["anchor_pending_alert"] is True

    for _ in range(3):  # a worker pass while the node is down must not raise
        await run_pass(db)
        await asyncio.sleep(0.1)

    retry = (await _doc(db, ctx)).get("anchor_retry") or {}
    assert retry.get("last_error") == "RPC_UNREACHABLE"
    assert retry.get("permanent") is False
    assert retry.get("attempts", 0) >= 1

    node.restart()
    await drive(db, lambda: _is_active(db, ctx))
    await _assert_anchored_exactly_once(db, ctx)


@hard_timeout(240)
async def test_tx_lost_when_node_is_killed_mid_anchor_is_dropped_and_resent(
    client, db, node, fast_anchor  # noqa: F811
):
    ctx = await _pending_approval(client, db)
    node.automine(False)  # the tx is accepted but sits unmined: "mid-anchor"
    body = await _approve(client, ctx)
    assert body["anchor_status"] == "PENDING"
    (first_row,) = await anchor_rows(db, ctx["document_id"])
    assert first_row["status"] == "PENDING"

    node.kill()
    await run_pass(db)  # confirm_tx raises ConnectionError here: must not propagate
    assert (await _doc(db, ctx))["status"] == "APPROVED"

    node.restart()  # fresh chain: the unmined tx is gone for good
    await drive(db, lambda: _is_active(db, ctx))

    rows = await anchor_rows(db, ctx["document_id"])
    assert rows[0]["_id"] == first_row["_id"]
    assert rows[0]["status"] == "FAILED" and rows[0]["error"] == "TX_DROPPED"
    await _assert_anchored_exactly_once(db, ctx)


@hard_timeout(120)
async def test_young_or_mempool_pending_tx_is_never_resent(client, db, node, fast_anchor):  # noqa: F811
    """A tx the node still knows about is waiting, not dropped, however old the row is.
    Legacy rows (no `live` field, D-023) must be respected too."""
    ctx = await _pending_approval(client, db)
    node.automine(False)
    await _approve(client, ctx)
    (row,) = await anchor_rows(db, ctx["document_id"])
    await db["blockchain_anchors"].update_one({"_id": row["_id"]}, {"$unset": {"live": ""}})

    nonce = wallet_nonce()
    await asyncio.sleep(2.0)  # longer than ANCHOR_PENDING_TIMEOUT_SEC (1.5)
    # Passes spread over time, not back to back: a wrongly-dropped tx would be re-sent as
    # soon as its (50 ms) backoff expires, so the window must outlast that backoff.
    for _ in range(8):
        await run_pass(db)
        await asyncio.sleep(0.1)
    assert wallet_nonce() == nonce, "a second tx was sent while the first was still pending"
    rows = await anchor_rows(db, ctx["document_id"])
    assert len(rows) == 1 and rows[0]["status"] == "PENDING", [r["status"] for r in rows]

    node.mine()
    await drive(db, lambda: _is_active(db, ctx))
    await _assert_anchored_exactly_once(db, ctx)


# --- 2. transient RPC failure, bounded retries ---------------------------------


@hard_timeout(120)
async def test_transient_failures_back_off_then_succeed_without_leaking_secrets(
    client, db, node, fast_anchor, caplog  # noqa: F811
):
    caplog.set_level(logging.DEBUG)
    ctx = await _pending_approval(client, db)
    real = chain.anchor_hash
    calls = {"n": 0}

    async def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] <= 3:  # call 1 is approve()'s own attempt; 2 and 3 are the worker's
            raise ConnectionError(LEAKY_RPC_ERROR)
        return await real(*args, **kwargs)

    with patch.object(chain, "anchor_hash", new=AsyncMock(side_effect=flaky)):
        await _approve(client, ctx)
        assert calls["n"] == 1

        await asyncio.sleep(0.1)
        await run_pass(db)
        first = (await _doc(db, ctx))["anchor_retry"]
        assert first["attempts"] == 1 and first["last_error"] == "RPC_UNREACHABLE"
        before = calls["n"]
        await run_pass(db)  # immediately again: still inside the backoff window
        assert calls["n"] == before, "retried before next_attempt_at"

        await asyncio.sleep(0.12)
        await run_pass(db)
        second = (await _doc(db, ctx))["anchor_retry"]
        assert second["attempts"] == 2
        delay1 = (naive(first["next_attempt_at"]) - naive(first["last_attempt_at"])).total_seconds()
        delay2 = (
            naive(second["next_attempt_at"]) - naive(second["last_attempt_at"])
        ).total_seconds()
        assert delay2 > delay1 > 0, (delay1, delay2)

        await drive(db, lambda: _is_active(db, ctx))

    await _assert_anchored_exactly_once(db, ctx)
    stored = everything_as_text(
        await anchor_rows(db, ctx["document_id"]),
        await _doc(db, ctx),
        await db["audit_logs"].find({}).to_list(None),
    )
    assert FAKE_SECRET not in stored and "alchemy" not in stored
    assert FAKE_SECRET not in caplog.text, "an RPC secret reached the logs"


@hard_timeout(120)
async def test_retries_are_bounded_then_permanently_failed(client, db, fast_anchor):  # noqa: F811
    ctx = await _pending_approval(client, db)
    failing = AsyncMock(side_effect=ConnectionError(LEAKY_RPC_ERROR))
    with patch.object(chain, "anchor_hash", new=failing):
        await _approve(client, ctx)
        await drive(db, lambda: _is_permanent(db, ctx))
        retry = (await _doc(db, ctx))["anchor_retry"]
        assert retry["attempts"] == 5  # ANCHOR_RETRY_MAX_ATTEMPTS in FAST_SETTINGS
        assert retry["permanent_reason"] == "RETRIES_EXHAUSTED"
        assert retry["last_error"] == "RPC_UNREACHABLE"

        sends = failing.await_count
        for _ in range(4):
            await run_pass(db)
            await asyncio.sleep(0.05)
        assert failing.await_count == sends, "kept retrying after permanent failure"

    document = await _doc(db, ctx)
    assert document["status"] == "APPROVED" and document["anchor_pending_alert"] is True
    rows = await anchor_rows(db, ctx["document_id"])
    assert FAKE_SECRET not in everything_as_text(rows, document)


# --- 3. permanent failure ------------------------------------------------------


@hard_timeout(120)
async def test_not_authorized_is_permanent_immediately_no_more_sends(
    client, db, node, fast_anchor  # noqa: F811
):
    ctx = await _pending_approval(client, db)
    use_wallet(NON_WRITER_KEY)  # a funded account the contract does not allow to anchor
    chain._w3 = None

    body = await _approve(client, ctx)
    assert body["anchor_status"] == "FAILED"
    retry = (await _doc(db, ctx)).get("anchor_retry") or {}
    assert retry.get("permanent") is True
    assert retry.get("permanent_reason") == "NOT_AUTHORIZED"

    nonce = wallet_nonce()
    spy = AsyncMock(wraps=chain.anchor_hash)
    with patch.object(chain, "anchor_hash", new=spy):
        for _ in range(3):
            await run_pass(db)
    assert spy.await_count == 0 and wallet_nonce() == nonce

    document = await _doc(db, ctx)
    assert document["status"] == "APPROVED" and document["anchor_pending_alert"] is True
    audit = await db["audit_logs"].find({"action": "ANCHOR_PERMANENT_FAIL"}).to_list(None)
    assert len(audit) == 1 and audit[0]["meta"]["error"] == "NOT_AUTHORIZED"


# --- a reverted receipt ----------------------------------------------------------


REVERTED_RECEIPT = {"block_number": 1, "status": 0}


@hard_timeout(120)
async def test_reverted_receipt_in_approve_fails_the_row_once_and_requeues(
    client, db, node, fast_anchor  # noqa: F811
):
    """The receipt claim is a compare-and-swap and hands the document to the worker. The revert
    is simulated at the receipt, so the chain really does hold the hash: the worker adopts it."""
    ctx = await _pending_approval(client, db)
    with patch.object(chain, "confirm_tx", new=AsyncMock(return_value=REVERTED_RECEIPT)):
        body = await _approve(client, ctx)
    assert body["anchor_status"] == "FAILED"

    (row,) = await anchor_rows(db, ctx["document_id"])
    assert row["status"] == "FAILED" and row["error"] == "REVERTED" and row["live"] is False
    document = await _doc(db, ctx)
    assert document["status"] == "APPROVED" and document["anchor_pending_alert"] is True
    retry = document["anchor_retry"]
    assert retry["last_error"] == "REVERTED" and retry["attempts"] == 0 and not retry["permanent"]

    await drive(db, lambda: _is_active(db, ctx))
    await _assert_anchored_exactly_once(db, ctx)


@hard_timeout(120)
async def test_worker_marks_a_reverted_pending_tx_failed_and_counts_one_attempt(
    client, db, node, fast_anchor  # noqa: F811
):
    ctx = await _pending_approval(client, db)
    node.automine(False)
    await _approve(client, ctx)
    (row,) = await anchor_rows(db, ctx["document_id"])
    assert row["status"] == "PENDING"

    with patch.object(chain, "confirm_tx", new=AsyncMock(return_value=REVERTED_RECEIPT)):
        await run_pass(db)
    (row,) = await anchor_rows(db, ctx["document_id"])
    assert row["status"] == "FAILED" and row["error"] == "REVERTED"
    retry = (await _doc(db, ctx))["anchor_retry"]
    assert retry["attempts"] == 1 and retry["last_error"] == "REVERTED" and not retry["permanent"]

    node.mine()  # the tx really was fine: the next attempt adopts what is on chain
    await drive(db, lambda: _is_active(db, ctx))
    await _assert_anchored_exactly_once(db, ctx)


# --- idempotency against the chain ---------------------------------------------


@hard_timeout(120)
async def test_hash_already_on_chain_is_adopted_not_resent(client, db, node, fast_anchor):  # noqa: F811
    """The tx landed but its response (and the row) were lost: the contract holds the
    hash, the DB has nothing. A retry must adopt it, not send a second transaction."""
    ctx = await _pending_approval(client, db)
    await chain.anchor_hash(ctx["document_id"], 1, PDF_SHA, 1)

    body = await _approve(client, ctx)
    assert body["anchor_status"] == "FAILED"
    (failed,) = await anchor_rows(db, ctx["document_id"])
    assert failed["error"] == "ALREADY_ANCHORED"

    nonce = wallet_nonce()
    await drive(db, lambda: _is_active(db, ctx))
    assert wallet_nonce() == nonce, "adoption must not send a transaction"

    rows = await anchor_rows(db, ctx["document_id"])
    adopted = [r for r in rows if r["status"] == "CONFIRMED"]
    assert len(adopted) == 1 and adopted[0].get("adopted") is True
    assert "tx_hash" not in adopted[0] or adopted[0]["tx_hash"] is None
    assert (await db["audit_logs"].count_documents({"action": "ANCHOR_ADOPTED"})) == 1
    await _assert_anchored_exactly_once(db, ctx)


@hard_timeout(120)
async def test_different_hash_on_chain_is_permanent_and_alerts(client, db, node, fast_anchor):  # noqa: F811
    ctx = await _pending_approval(client, db)
    await chain.anchor_hash(ctx["document_id"], 1, "ff" * 32, 1)  # someone else's hash
    await _approve(client, ctx)

    nonce = wallet_nonce()
    await drive(db, lambda: _is_permanent(db, ctx))
    assert wallet_nonce() == nonce
    retry = (await _doc(db, ctx))["anchor_retry"]
    assert retry["permanent_reason"] == "ALREADY_ANCHORED"
    document = await _doc(db, ctx)
    assert document["status"] == "APPROVED" and document["anchor_pending_alert"] is True
    assert (await db["audit_logs"].count_documents({"action": "ANCHOR_PERMANENT_FAIL"})) == 1


@hard_timeout(120)
async def test_confirmed_anchor_under_approved_document_is_promoted_not_resent(
    client, db, node, fast_anchor  # noqa: F811
):
    """A crash between 'anchor CONFIRMED' and the rest of the promotion."""
    ctx = await _pending_approval(client, db)
    await _approve(client, ctx)
    assert await _is_active(db, ctx)

    document_id, version_id = ObjectId(ctx["document_id"]), ObjectId(ctx["version_id"])
    await db["documents"].update_one(
        {"_id": document_id},
        {
            "$set": {"status": "APPROVED", "anchor_pending_alert": True},
            "$unset": {"current_version_id": ""},
        },
    )
    await db["document_versions"].update_one(
        {"_id": version_id},
        {"$set": {"status": "APPROVED", "anchored": False}, "$unset": {"anchor_id": ""}},
    )

    nonce = wallet_nonce()
    await drive(db, lambda: _is_active(db, ctx))
    assert wallet_nonce() == nonce
    await _assert_anchored_exactly_once(db, ctx)


# --- the stored-object pre-check (D-039) ---------------------------------------


@hard_timeout(120)
async def test_missing_stored_object_is_permanent_and_nothing_is_sent(client, db, fast_anchor):  # noqa: F811
    ctx = await _pending_approval(client, db)
    await _approve_with_failing_send(client, ctx)
    version = await db["document_versions"].find_one({"_id": ObjectId(ctx["version_id"])})
    storage.delete_object(version["storage_key"])

    spy = AsyncMock(wraps=chain.anchor_hash)
    with patch.object(chain, "anchor_hash", new=spy):
        await asyncio.sleep(0.1)
        await drive(db, lambda: _is_permanent(db, ctx))
    assert spy.await_count == 0
    assert (await _doc(db, ctx))["anchor_retry"]["permanent_reason"] == "STORED_OBJECT_MISSING"


@hard_timeout(120)
async def test_storage_outage_is_transient_not_a_missing_object(client, db, node, fast_anchor):  # noqa: F811
    ctx = await _pending_approval(client, db)
    await _approve_with_failing_send(client, ctx)

    with patch.object(storage, "object_exists", side_effect=RuntimeError("storage down")):
        await asyncio.sleep(0.1)
        await run_pass(db)
        retry = (await _doc(db, ctx))["anchor_retry"]
        assert retry["permanent"] is False and retry["attempts"] == 1
    await drive(db, lambda: _is_active(db, ctx))  # storage is back: it anchors
    await _assert_anchored_exactly_once(db, ctx)


# --- 4. two workers racing -----------------------------------------------------


@hard_timeout(120)
async def test_two_workers_in_one_process_send_exactly_one_tx(client, db, node, fast_anchor):  # noqa: F811
    ctx = await _pending_approval(client, db)
    await _approve_with_failing_send(client, ctx)
    await asyncio.sleep(0.15)  # past the first backoff

    spy = AsyncMock(wraps=chain.anchor_hash)
    with patch.object(chain, "anchor_hash", new=spy):
        await asyncio.gather(*(run_pass(db) for _ in range(4)))
        assert spy.await_count == 1, f"expected exactly one send, got {spy.await_count}"
        await drive(db, lambda: _is_active(db, ctx))
    await _assert_anchored_exactly_once(db, ctx)


@hard_timeout(180)
async def test_two_worker_processes_race_for_the_same_document(client, db, node, fast_anchor):  # noqa: F811
    """Two real OS processes (so no shared asyncio lock, no shared nonce lock)."""
    ctx = await _pending_approval(client, db)
    await _approve_with_failing_send(client, ctx)
    await asyncio.sleep(0.15)

    env = os.environ.copy()
    # Safety: these processes must only ever see the test DB and the local node.
    assert env["MONGODB_DB"] == "geolegalvault_test"
    assert env["SEPOLIA_RPC_URL"].startswith("http://127.0.0.1")
    command = [sys.executable, "-m", "app.workers.anchor_confirmer", "--once"]
    procs = [
        subprocess.Popen(
            command,
            cwd=BACKEND_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for _ in range(2)
    ]

    async def _finish(proc: subprocess.Popen) -> tuple[int, str]:
        try:
            out, _ = await asyncio.to_thread(proc.communicate, timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _ = proc.communicate()
            pytest.fail(f"worker did not exit in 60s (it must support --once):\n{out[-1500:]}")
        return proc.returncode, out

    results = await asyncio.gather(*(_finish(p) for p in procs))
    for code, out in results:
        assert code == 0, out[-1500:]
        assert FAKE_SECRET not in out
        assert get_settings().SEPOLIA_RPC_URL not in out

    await drive(db, lambda: _is_active(db, ctx))  # a loser's nonce collision just retries
    await _assert_anchored_exactly_once(db, ctx)
    live = await db["blockchain_anchors"].count_documents(
        {"document_id": ObjectId(ctx["document_id"]), "live": True}
    )
    assert live == 1


# --- the loop itself -----------------------------------------------------------


@hard_timeout(60)
async def test_run_forever_survives_errors_and_keeps_a_heartbeat(db, fast_anchor):  # noqa: F811
    from app.workers import anchor_confirmer as worker

    calls = {"n": 0}
    real = worker.confirm_pending_anchors

    async def flaky(database):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise ConnectionError(LEAKY_RPC_ERROR)
        return await real(database)

    with patch.object(worker, "confirm_pending_anchors", new=flaky):
        task = asyncio.create_task(worker.run_forever(db, interval_sec=0.02))
        try:
            for _ in range(200):
                await asyncio.sleep(0.05)
                beat = await db["worker_heartbeats"].find_one({"_id": "anchor_worker"})
                if calls["n"] >= 4 and beat and beat.get("last_ok_at"):
                    break
            assert not task.done(), f"the worker died: {task.exception() if task.done() else ''}"
            assert calls["n"] >= 4
            assert beat is not None and beat["last_error_code"] == "RPC_UNREACHABLE"
            assert beat["last_ok_at"] is not None
            assert FAKE_SECRET not in everything_as_text(beat)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@hard_timeout(60)
async def test_a_lease_held_by_a_live_worker_blocks_others_until_it_expires(
    client, db, node, fast_anchor  # noqa: F811
):
    ctx = await _pending_approval(client, db)
    await _approve_with_failing_send(client, ctx)
    document_id = ObjectId(ctx["document_id"])
    future = naive(datetime.now(UTC)) + timedelta(seconds=30)
    await db["documents"].update_one(
        {"_id": document_id},
        {
            "$set": {
                "anchor_retry.lease_owner": "another-worker",
                "anchor_retry.lease_until": future,
            }
        },
    )
    await asyncio.sleep(0.15)

    spy = AsyncMock(wraps=chain.anchor_hash)
    with patch.object(chain, "anchor_hash", new=spy):
        await run_pass(db)
        assert spy.await_count == 0, "took a document another worker holds the lease for"

        # a crashed worker: its lease is in the past, so the document is picked up again
        await db["documents"].update_one(
            {"_id": document_id},
            {"$set": {"anchor_retry.lease_until": naive(datetime.now(UTC)) - timedelta(seconds=5)}},
        )
        await run_pass(db)
        assert spy.await_count == 1
