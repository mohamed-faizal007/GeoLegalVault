"""SEC-02 / D-051: scripts/classification_migration.py is a dry run unless told otherwise, never
guesses an unrecognised value, and never touches a clearance that is already valid.

Runs against the throwaway test database only (conftest sets MONGODB_DB); no `.env` needed.
"""

import importlib.util
import sys
from pathlib import Path

import pytest
from pymongo import MongoClient

from app.core.config import get_settings

pytestmark = pytest.mark.asyncio(loop_scope="session")

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "classification_migration.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("classification_migration", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def sync_db():
    settings = get_settings()
    assert settings.MONGODB_DB == "geolegalvault_test"  # never the dev database
    client = MongoClient(settings.MONGODB_URI)
    yield client[settings.MONGODB_DB]
    client.close()


def _seed(sync_db):
    docs = [
        ("exact", "RESTRICTED"),
        ("lower", "restricted"),
        ("spaced", "Top Secret"),
        ("odd", "SECRET"),
        ("missing", None),
    ]
    ids = {}
    for name, value in docs:
        doc = {"title": name}
        if value is not None:
            doc["classification"] = value
        ids[name] = sync_db["documents"].insert_one(doc).inserted_id
    users = {
        "admin": {"email": "a@x.test", "role": "ADMINISTRATOR"},
        "staff": {"email": "s@x.test", "role": "AUTHORIZED_STAFF"},
        "has": {"email": "h@x.test", "role": "LEGAL_OFFICER", "clearance": "TOP_SECRET"},
        "bad": {"email": "b@x.test", "role": "AUDITOR", "clearance": "GOD_MODE"},
    }
    uids = {k: sync_db["users"].insert_one(dict(v)).inserted_id for k, v in users.items()}
    return ids, uids


def _snapshot(sync_db):
    return (
        list(sync_db["documents"].find().sort("_id", 1)),
        list(sync_db["users"].find().sort("_id", 1)),
        sync_db["audit_logs"].count_documents({}),
    )


def _run(monkeypatch, capsys, *args):
    module = _load_script()
    monkeypatch.setattr(sys, "argv", ["classification_migration.py", *args])
    module.main()
    return capsys.readouterr().out


async def test_a_dry_run_writes_nothing_and_lists_what_it_would_do(sync_db, monkeypatch, capsys):
    _seed(sync_db)
    before = _snapshot(sync_db)

    out = _run(monkeypatch, capsys)

    assert _snapshot(sync_db) == before
    assert "DRY RUN" in out and "Nothing was written" in out
    assert "'restricted' -> 'RESTRICTED'" in out and "case normalised" in out
    assert "'Top Secret'" in out and "'SECRET'" in out  # listed as not guessed
    assert "a@x.test" in out and "INTERNAL" in out  # a proposal for the administrator


async def test_apply_changes_only_what_was_listed_and_never_guesses(sync_db, monkeypatch, capsys):
    ids, uids = _seed(sync_db)

    _run(monkeypatch, capsys, "--apply", "--user-clearance", "s@x.test=INTERNAL")

    value = {d["title"]: d.get("classification") for d in sync_db["documents"].find()}
    assert value["exact"] == "RESTRICTED"
    assert value["lower"] == "RESTRICTED"  # case only
    assert value["spaced"] == "Top Secret"  # not guessed
    assert value["odd"] == "SECRET"  # not guessed
    assert value["missing"] is None  # not guessed
    users = {u["email"]: u.get("clearance") for u in sync_db["users"].find()}
    assert users["a@x.test"] == "INTERNAL"  # proposed by role
    assert users["s@x.test"] == "INTERNAL"  # explicit override
    assert users["h@x.test"] == "TOP_SECRET"  # a valid clearance is never touched
    assert users["b@x.test"] == "RESTRICTED"  # invalid -> the proposal for AUDITOR
    actions = sorted(r["action"] for r in sync_db["audit_logs"].find())
    assert actions == ["CLASSIFICATION_MIGRATED"] + ["CLEARANCE_MIGRATED"] * 3
    assert ids and uids


async def test_an_explicit_mapping_is_applied_and_a_bad_level_is_refused(
    sync_db, monkeypatch, capsys
):
    _seed(sync_db)

    _run(monkeypatch, capsys, "--apply", "--map", "Top Secret=TOP_SECRET")
    value = {d["title"]: d.get("classification") for d in sync_db["documents"].find()}
    assert value["spaced"] == "TOP_SECRET"
    assert value["odd"] == "SECRET"

    with pytest.raises(SystemExit):
        _run(monkeypatch, capsys, "--map", "SECRET=SUPER_SECRET")
