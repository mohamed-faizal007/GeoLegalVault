"""Operating the worker (D-040): --dry-run is strictly read-only, the heartbeat feeds
/health and --healthcheck. No Hardhat node is needed; the chain is mocked at its
read boundary and `anchor_hash` is asserted never to run in a dry run.
"""

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

from app.services import blockchain as chain
from app.services import storage
from tests.integration.anchor_helpers import (
    FAKE_SECRET,
    LEAKY_RPC_ERROR,
    anchor_rows,
    everything_as_text,
    fast_anchor,  # noqa: F401 (fixture)
    hard_timeout,
)
from tests.integration.test_concurrency import _pending_approval
from tests.integration.test_workflow import _auth, _geo

pytestmark = pytest.mark.asyncio(loop_scope="session")

BACKEND_DIR = Path(__file__).resolve().parents[2]
WATCHED = (
    "documents",
    "blockchain_anchors",
    "audit_logs",
    "worker_heartbeats",
    "document_versions",
)
NO_ANCHOR = {"exists": False, "hash": "0x" + "00" * 32, "event_type": 0, "ts": 0}


async def _stuck(client, db) -> dict:
    ctx = await _pending_approval(client, db)
    failing = AsyncMock(side_effect=ConnectionError(LEAKY_RPC_ERROR))
    with patch.object(chain, "anchor_hash", new=failing):
        response = await client.post(
            f"/api/v1/documents/{ctx['document_id']}/approve",
            headers={**_auth(ctx["approvers"][0]), **_geo()},
        )
    assert response.status_code == 200, response.text
    return ctx


async def _snapshot(db) -> dict:
    return {name: await db[name].find({}).sort("_id", 1).to_list(None) for name in WATCHED}


# --- --dry-run -------------------------------------------------------------------


@hard_timeout(120)
async def test_dry_run_lists_what_it_would_do_and_changes_nothing(client, db, fast_anchor):  # noqa: F811
    from app.workers import anchor_confirmer as worker

    fresh = await _stuck(client, db)
    # the shape of the dev DB's "Approval Demo": old, and its stored object is gone
    old = datetime.now(UTC) - timedelta(days=36)
    await db["documents"].update_one(
        {"_id": ObjectId(fresh["document_id"])},
        {"$set": {"anchor_retry.queued_at": old, "anchor_retry.next_attempt_at": old}},
    )
    version = await db["document_versions"].find_one({"_id": ObjectId(fresh["version_id"])})
    storage.delete_object(version["storage_key"])

    before = await _snapshot(db)
    spy = AsyncMock(side_effect=AssertionError("a dry run must never send"))
    onchain = AsyncMock(return_value=NO_ANCHOR)
    with (
        patch.object(chain, "anchor_hash", new=spy),
        patch.object(chain, "get_onchain_anchor", new=onchain),
        patch.object(chain, "get_service_account", side_effect=AssertionError("never sign")),
    ):
        plan = await worker.plan_dry_run(db)

    assert await _snapshot(db) == before, "a dry run wrote to the database"
    assert spy.await_count == 0
    (entry,) = plan
    assert entry["document_id"] == fresh["document_id"] and entry["version_no"] == 1
    assert entry["would_send"] is False
    assert entry["action"] == "NEEDS_ADMIN_RETRY"
    assert entry["chain_has_hash"] is False and entry["object_exists"] is False
    assert FAKE_SECRET not in everything_as_text(plan)


@hard_timeout(120)
async def test_dry_run_says_would_send_for_a_young_document_and_still_sends_nothing(
    client, db, fast_anchor  # noqa: F811
):
    from app.workers import anchor_confirmer as worker

    ctx = await _stuck(client, db)
    before = await _snapshot(db)
    spy = AsyncMock(side_effect=AssertionError("a dry run must never send"))
    onchain = AsyncMock(return_value=NO_ANCHOR)
    with (
        patch.object(chain, "anchor_hash", new=spy),
        patch.object(chain, "get_onchain_anchor", new=onchain),
    ):
        plan = await worker.plan_dry_run(db)

    assert await _snapshot(db) == before and spy.await_count == 0
    (entry,) = plan
    assert entry["document_id"] == ctx["document_id"]
    assert entry["action"] == "WOULD_SEND" and entry["would_send"] is True
    assert entry["object_exists"] is True and entry["chain_has_hash"] is False


@hard_timeout(120)
async def test_dry_run_cli_prints_the_plan_and_exits_zero(client, db, fast_anchor):  # noqa: F811
    ctx = await _stuck(client, db)
    old = datetime.now(UTC) - timedelta(days=36)
    await db["documents"].update_one(
        {"_id": ObjectId(ctx["document_id"])},
        {"$set": {"anchor_retry.queued_at": old, "anchor_retry.next_attempt_at": old}},
    )
    before = await _snapshot(db)

    env = os.environ.copy()
    assert env["MONGODB_DB"] == "geolegalvault_test"
    env["SEPOLIA_RPC_URL"] = "http://127.0.0.1:1"  # refused instantly: never the public node
    result = subprocess.run(
        [sys.executable, "-m", "app.workers.anchor_confirmer", "--dry-run"],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert ctx["document_id"] in result.stdout
    assert "NEEDS_ADMIN_RETRY" in result.stdout
    assert "127.0.0.1:1" not in result.stdout + result.stderr  # no RPC URL printed
    assert await _snapshot(db) == before


# --- heartbeat, /health, --healthcheck --------------------------------------------------


async def _health(client) -> dict:
    return (await client.get("/api/v1/health")).json()


async def test_health_reports_stale_until_the_worker_beats_and_stale_again_when_it_stops(
    client, db
):
    from app.workers import heartbeat

    assert (await _health(client))["anchor_worker"] == "stale"  # never ran

    await heartbeat.beat(db)
    health = await _health(client)
    assert health["anchor_worker"] == "ok"
    assert set(health) == {"status", "mongo", "storage", "chain", "anchor_worker"}

    await db["worker_heartbeats"].update_one(
        {"_id": "anchor_worker"},
        {"$set": {"last_beat_at": datetime.now(UTC) - timedelta(minutes=10)}},
    )
    assert (await _health(client))["anchor_worker"] == "stale"


async def test_a_stale_worker_does_not_degrade_overall_health(client, db):
    """The worker is optional (Guardrail #10): its absence must not read as an outage."""
    body = await _health(client)
    assert body["anchor_worker"] == "stale"
    infra_ok = body["mongo"] == "reachable" and body["storage"] == "reachable"
    assert body["status"] == ("ok" if infra_ok else "degraded")


async def test_heartbeat_records_an_error_code_never_the_message(db):
    from app.workers import heartbeat

    await heartbeat.beat(db, error=ConnectionError(LEAKY_RPC_ERROR))
    beat = await db["worker_heartbeats"].find_one({"_id": "anchor_worker"})
    assert beat["last_error_code"] == "RPC_UNREACHABLE"
    assert FAKE_SECRET not in everything_as_text(beat)

    # the last error stays visible (with when it happened); a clean loop stamps last_ok_at after it
    await heartbeat.beat(db)
    beat = await db["worker_heartbeats"].find_one({"_id": "anchor_worker"})
    assert beat["last_error_code"] == "RPC_UNREACHABLE"
    assert beat["last_ok_at"] >= beat["last_error_at"]


@hard_timeout(60)
async def test_healthcheck_cli_exit_codes_follow_heartbeat_age(db):
    from app.workers import heartbeat

    env = os.environ.copy()
    assert env["MONGODB_DB"] == "geolegalvault_test"
    command = [sys.executable, "-m", "app.workers.anchor_confirmer", "--healthcheck"]

    def run() -> int:
        result = subprocess.run(
            command, cwd=BACKEND_DIR, env=env, capture_output=True, timeout=45
        )
        return result.returncode

    import asyncio

    assert await asyncio.to_thread(run) == 1  # no heartbeat
    await heartbeat.beat(db)
    assert await asyncio.to_thread(run) == 0
    await db["worker_heartbeats"].update_one(
        {"_id": "anchor_worker"},
        {"$set": {"last_beat_at": datetime.now(UTC) - timedelta(minutes=10)}},
    )
    assert await asyncio.to_thread(run) == 1


async def test_approve_failure_enqueues_the_document_for_the_worker(client, db, fast_anchor):  # noqa: F811
    ctx = await _stuck(client, db)
    document = await db["documents"].find_one({"_id": ObjectId(ctx["document_id"])})
    retry = document["anchor_retry"]
    assert retry["permanent"] is False and retry["attempts"] == 0
    assert retry["queued_at"] is not None and retry["next_attempt_at"] is not None
    assert retry["last_error"] == "RPC_UNREACHABLE"
    assert len(await anchor_rows(db, ctx["document_id"])) == 1
