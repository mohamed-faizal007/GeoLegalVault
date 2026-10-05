"""SEC-02 / D-051: bring existing data in line with fixed classification levels and clearances.

DRY RUN BY DEFAULT: with no flag this only READS the database and prints what it would change.
Nothing is written unless you pass --apply, and --apply is meant to be run only after the dry
run has been reviewed.

What it does
  Documents  `classification` must be one of PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED,
             TOP_SECRET. An exact level is left alone. A value that differs only by case
             (e.g. "restricted") is normalised. ANYTHING ELSE IS NOT GUESSED: it is listed, and
             stays as it is (hidden from every role) until you give an explicit mapping with
             --map "Old value=LEVEL" (repeatable).
  Users      a user with no (or an invalid) `clearance` gets a PROPOSED level by role. A valid
             existing clearance is never touched. --user-clearance EMAIL=LEVEL (repeatable)
             overrides the proposal for one user. Nobody gets TOP_SECRET unless you say so.

Usage (from the repo root, backend venv active):
    python scripts/classification_migration.py                       # dry run
    python scripts/classification_migration.py --map "Top Secret=TOP_SECRET" \
        --user-clearance admin@example.com=RESTRICTED                # still a dry run
    python scripts/classification_migration.py --apply [same options]

Each applied change writes one audit row (CLASSIFICATION_MIGRATED / CLEARANCE_MIGRATED, actor
SYSTEM). Titles are printed for the dry run only so you can recognise documents; nothing is sent
anywhere.
"""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from pymongo import MongoClient  # noqa: E402

from app.core.clearance import LEVELS, PROPOSED_ROLE_CLEARANCE, rank_of  # noqa: E402
from app.core.config import get_settings  # noqa: E402


def _parse_pairs(items: list[str], what: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            sys.exit(f"{what} expects KEY=VALUE, got {item!r}")
        key, value = item.rsplit("=", 1)
        pairs[key] = value
    return pairs


def plan_documents(db, mapping: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """(changes, unmapped): a change is {id, title, from, to, how}, unmapped {id, title, value}."""
    changes: list[dict] = []
    unmapped: list[dict] = []
    for doc in db["documents"].find({}, {"title": 1, "classification": 1}):
        value = doc.get("classification")
        if rank_of(value) is not None:
            continue
        if value in mapping:
            changes.append(
                {
                    "id": doc["_id"],
                    "title": doc.get("title"),
                    "from": value,
                    "to": mapping[value],
                    "how": "explicit --map",
                }
            )
        elif (
            isinstance(value, str) and rank_of(value.upper()) is not None and value == value.strip()
        ):
            changes.append(
                {
                    "id": doc["_id"],
                    "title": doc.get("title"),
                    "from": value,
                    "to": value.upper(),
                    "how": "case normalised",
                }
            )
        else:
            unmapped.append({"id": doc["_id"], "title": doc.get("title"), "value": value})
    return changes, unmapped


def plan_users(db, overrides: dict[str, str]) -> list[dict]:
    changes: list[dict] = []
    for user in db["users"].find({}, {"email": 1, "role": 1, "clearance": 1}):
        if rank_of(user.get("clearance")) is not None:
            continue
        proposed = overrides.get(user["email"]) or PROPOSED_ROLE_CLEARANCE.get(
            user.get("role"), "PUBLIC"
        )
        changes.append(
            {
                "id": user["_id"],
                "email": user["email"],
                "role": user.get("role"),
                "from": user.get("clearance"),
                "to": proposed,
                "how": "explicit --user-clearance"
                if user["email"] in overrides
                else "proposed by role",
            }
        )
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    parser.add_argument("--map", action="append", default=[], metavar="OLD=LEVEL")
    parser.add_argument("--user-clearance", action="append", default=[], metavar="EMAIL=LEVEL")
    args = parser.parse_args()

    mapping = _parse_pairs(args.map, "--map")
    overrides = _parse_pairs(args.user_clearance, "--user-clearance")
    for what, values in (("--map", mapping), ("--user-clearance", overrides)):
        for level in values.values():
            if rank_of(level) is None:
                sys.exit(f"{what}: {level!r} is not one of {', '.join(LEVELS)}")

    settings = get_settings()
    client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = client[settings.MONGODB_DB]

    total = db["documents"].count_documents({})
    distribution = {
        row["_id"]: row["n"]
        for row in db["documents"].aggregate(
            [{"$group": {"_id": "$classification", "n": {"$sum": 1}}}]
        )
    }
    doc_changes, unmapped = plan_documents(db, mapping)
    user_changes = plan_users(db, overrides)

    print(f"MODE: {'APPLY (writes!)' if args.apply else 'DRY RUN (read-only)'}")
    print(f"\nDocuments: {total} total. Current classification values:")
    for value, count in sorted(distribution.items(), key=lambda kv: -kv[1]):
        marker = "ok " if rank_of(value) is not None else "!! "
        print(f"  {marker}{value!r}: {count}")

    print(f"\nDocuments that WOULD be changed: {len(doc_changes)}")
    for change in doc_changes:
        print(
            f"  {change['id']}  {change['title']!r}: "
            f"{change['from']!r} -> {change['to']!r}  ({change['how']})"
        )
    print(
        "\nDocuments with a value that is NOT guessed "
        f"(left as is, hidden from everyone): {len(unmapped)}"
    )
    for item in unmapped:
        value = f"{item['value']!r}   (use --map to choose a level)"
        print(f"  {item['id']}  {item['title']!r}: {value}")

    print(f"\nUsers that WOULD get a clearance: {len(user_changes)}")
    for change in user_changes:
        print(
            f"  {change['email']:<40} {str(change['role']):<18} "
            f"{change['from']!r} -> {change['to']}  ({change['how']})"
        )
    already = db["users"].count_documents({}) - len(user_changes)
    print(f"Users that already have a valid clearance (untouched): {already}")

    if not args.apply:
        print("\nDry run only. Nothing was written. Re-run with --apply to write these changes.")
        return

    now = datetime.now(UTC)
    for change in doc_changes:
        db["documents"].update_one(
            {"_id": change["id"]}, {"$set": {"classification": change["to"]}}
        )
        db["audit_logs"].insert_one(
            {
                "actor_id": "SYSTEM",
                "action": "CLASSIFICATION_MIGRATED",
                "target_type": "document",
                "target_id": change["id"],
                "result": "SUCCESS",
                "ip": None,
                "location": None,
                "meta": {"from": change["from"], "to": change["to"], "how": change["how"]},
                "created_at": now,
            }
        )
    for change in user_changes:
        db["users"].update_one({"_id": change["id"]}, {"$set": {"clearance": change["to"]}})
        db["audit_logs"].insert_one(
            {
                "actor_id": "SYSTEM",
                "action": "CLEARANCE_MIGRATED",
                "target_type": "user",
                "target_id": str(change["id"]),
                "result": "SUCCESS",
                "ip": None,
                "location": None,
                "meta": {"from": change["from"], "to": change["to"], "how": change["how"]},
                "created_at": now,
            }
        )
    print(f"\nApplied: {len(doc_changes)} document(s), {len(user_changes)} user(s).")


if __name__ == "__main__":
    main()
