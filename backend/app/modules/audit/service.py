"""audit module service layer — the append-only security audit trail
(Plan Parts 20, 32).

`record()` is the one call site every lifecycle transition (Phase 6) and
every other security-relevant action (Phases 1-7, and this phase) uses.
Phases 1-7 called this function while it was still a no-op stub; its body
is implemented here without any of those call sites changing — they
already pass exactly the fields this collection stores.

This module exposes exactly one write path (`record`, an insert) and one
read path (`list_audit_logs`, a find). There is intentionally no
update/delete function — the append-only guarantee is enforced by this
module simply never defining one, and by the router (router.py) exposing
only GET.
"""

import re
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.clearance import can_see
from app.core.db import get_database
from app.modules.audit.models import AUDIT_LOGS_COLLECTION
from app.modules.audit.schemas import AuditLogOut
from app.modules.users import service as users_service
from app.modules.users.models import USERS_COLLECTION


async def record(
    *,
    actor_id: Any,
    action: str,
    target_type: str,
    target_id: Any,
    result: str = "SUCCESS",
    ip: str | None = None,
    location: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Append one audit record. Mongo is already a hard dependency of every
    caller here, so an insert failure surfaces like any other DB error."""
    doc: dict[str, Any] = {
        "actor_id": actor_id,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "result": result,
        "ip": ip,
        "meta": meta or {},
        "created_at": datetime.now(UTC),
    }
    if location is not None:
        # Stored only when present: a 2dsphere index treats a *missing*
        # field as "not geolocated" and skips it, but an explicit null can
        # trip index/query errors — so we simply never write the key.
        doc["location"] = location
    db = get_database()
    await db[AUDIT_LOGS_COLLECTION].insert_one(doc)


def _id_filter(value: str) -> Any:
    """actor_id/target_id are stored as whatever the caller passed —
    usually a Mongo ObjectId, sometimes a literal string ("SYSTEM" for
    system-triggered anchoring, or an email for a failed login where no
    user id exists yet). Match either representation of the same value."""
    try:
        return {"$in": [value, ObjectId(value)]}
    except InvalidId:
        return value


async def hidden_row_ids(
    db: AsyncIOMotorDatabase, viewer: dict[str, Any], rows: list[dict[str, Any]]
) -> set[Any]:
    """Ids of audit rows whose target is a document (or a version of one) that is above the
    viewer's clearance (D-051). Such rows stay visible, so oversight of who did what is not
    blinded, but their `meta` (review comments, reasons, tx data) is withheld. A target that
    cannot be found, or is not a document, has nothing to protect."""
    from app.modules.documents.models import DOCUMENTS_COLLECTION
    from app.modules.versions.models import DOCUMENT_VERSIONS_COLLECTION

    doc_ids: set[Any] = set()
    version_ids: set[Any] = set()
    for row in rows:
        target = row.get("target_id")
        if isinstance(target, ObjectId):
            if row.get("target_type") == "document":
                doc_ids.add(target)
            elif row.get("target_type") == "version":
                version_ids.add(target)

    version_to_doc: dict[Any, Any] = {}
    if version_ids:
        cursor = db[DOCUMENT_VERSIONS_COLLECTION].find(
            {"_id": {"$in": list(version_ids)}}, {"document_id": 1}
        )
        version_to_doc = {v["_id"]: v["document_id"] async for v in cursor}
    all_doc_ids = doc_ids | set(version_to_doc.values())
    classification: dict[Any, Any] = {}
    if all_doc_ids:
        cursor = db[DOCUMENTS_COLLECTION].find(
            {"_id": {"$in": list(all_doc_ids)}}, {"classification": 1}
        )
        classification = {d["_id"]: d.get("classification") async for d in cursor}

    def hidden(document_id: Any) -> bool:
        return document_id in classification and not can_see(viewer, classification[document_id])

    hidden_rows: set[Any] = set()
    for row in rows:
        target = row.get("target_id")
        if row.get("target_type") == "document" and hidden(target):
            hidden_rows.add(row["_id"])
        elif row.get("target_type") == "version" and hidden(version_to_doc.get(target)):
            hidden_rows.add(row["_id"])
    return hidden_rows


async def resolve_labels(
    db: AsyncIOMotorDatabase, viewer: dict[str, Any], rows: list[dict[str, Any]]
) -> tuple[dict[Any, dict[str, Any]], dict[Any, str]]:
    """Readable names for the actors and targets on one page of rows (D-054). Two batched
    lookups, bounded by the page size. Read-time, so a renamed user shows the current name and
    a user who no longer exists shows no label (the UI then shows the id); nothing stored in
    `audit_logs` changes. A document title is a label only where `can_see` allows it, the same
    rule as everywhere else (D-051), so a label can never reveal a hidden document."""
    from app.modules.documents.models import DOCUMENTS_COLLECTION
    from app.modules.versions.models import DOCUMENT_VERSIONS_COLLECTION

    user_ids = {r.get("actor_id") for r in rows}
    doc_ids: set[Any] = set()
    version_ids: set[Any] = set()
    for row in rows:
        target = row.get("target_id")
        if not isinstance(target, ObjectId):
            continue
        kind = row.get("target_type")
        if kind == "user":
            user_ids.add(target)
        elif kind == "document":
            doc_ids.add(target)
        elif kind == "version":
            version_ids.add(target)
    users = await users_service.identities_by_id(db, user_ids)

    versions: dict[Any, dict[str, Any]] = {}
    if version_ids:
        cursor = db[DOCUMENT_VERSIONS_COLLECTION].find(
            {"_id": {"$in": list(version_ids)}}, {"document_id": 1, "version_no": 1}
        )
        versions = {v["_id"]: v async for v in cursor}
    all_doc_ids = doc_ids | {v["document_id"] for v in versions.values()}
    documents: dict[Any, dict[str, Any]] = {}
    if all_doc_ids:
        cursor = db[DOCUMENTS_COLLECTION].find(
            {"_id": {"$in": list(all_doc_ids)}}, {"title": 1, "classification": 1}
        )
        documents = {d["_id"]: d async for d in cursor}

    def title(document_id: Any) -> str | None:
        document = documents.get(document_id)
        if document is None or not can_see(viewer, document.get("classification")):
            return None
        return document["title"]

    labels: dict[Any, str] = {}
    for row in rows:
        target = row.get("target_id")
        kind = row.get("target_type")
        label: str | None = None
        if kind == "user" and target in users:
            label = users_service.display_name(users[target])
        elif kind == "document":
            label = title(target)
        elif kind == "version" and target in versions:
            name = title(versions[target]["document_id"])
            label = f"{name} · v{versions[target]['version_no']}" if name else None
        if label:
            labels[row["_id"]] = label
    return users, labels


def to_out(
    doc: dict[str, Any],
    *,
    redacted: bool = False,
    users: dict[Any, dict[str, Any]] | None = None,
    target_label: str | None = None,
) -> AuditLogOut:
    actor = (users or {}).get(doc.get("actor_id"))
    actor_id = doc.get("actor_id")
    # A failed login stores the typed email as the actor and "SYSTEM" is a literal: both are
    # already readable, so they are their own label. Only an ObjectId needs resolving.
    label = (
        users_service.display_name(actor)
        if actor
        else (actor_id if isinstance(actor_id, str) else None)
    )
    return AuditLogOut(
        id=str(doc["_id"]),
        actor_id=str(doc["actor_id"]) if doc.get("actor_id") is not None else None,
        actor_label=label,
        actor_email=actor["email"] if actor else None,
        action=doc["action"],
        target_type=doc["target_type"],
        target_id=str(doc["target_id"]) if doc.get("target_id") is not None else None,
        target_label=target_label,
        result=doc["result"],
        ip=doc.get("ip"),
        location=doc.get("location"),
        meta={} if redacted else (doc.get("meta") or {}),
        redacted=redacted,
        created_at=doc["created_at"],
    )


_ACTOR_SEARCH_MAX_USERS = 50


async def _actor_search_ids(db: AsyncIOMotorDatabase, text: str) -> list[Any]:
    """Every stored form of the actors whose name or email contains `text` (D-054): their
    ObjectId, its string form and their email (a failed login stores the typed email). Bounded
    to `_ACTOR_SEARCH_MAX_USERS` users; the text is escaped, never used as a pattern."""
    pattern = {"$regex": re.escape(text.strip()), "$options": "i"}
    cursor = (
        db[USERS_COLLECTION]
        .find({"$or": [{"name": pattern}, {"email": pattern}]}, {"email": 1})
        .limit(_ACTOR_SEARCH_MAX_USERS)
    )
    ids: list[Any] = []
    async for user in cursor:
        ids += [user["_id"], str(user["_id"]), user["email"]]
    if "@" in text:
        ids.append(text.strip().lower())  # a failed login for an address that is not a user
    return ids


async def _document_target_ids(db: AsyncIOMotorDatabase, document_id: str) -> list[Any]:
    """The document and each of its versions: both appear as audit targets."""
    from app.modules.versions.models import DOCUMENT_VERSIONS_COLLECTION

    oid = ObjectId(document_id)
    cursor = db[DOCUMENT_VERSIONS_COLLECTION].find({"document_id": oid}, {"_id": 1})
    return [oid, document_id, *[v["_id"] async for v in cursor]]


async def list_actions(db: AsyncIOMotorDatabase) -> list[str]:
    """The distinct action names recorded so far, for the filter dropdown. `action` is indexed
    and the set is a few dozen strings, so this stays cheap however many rows there are."""
    return sorted(await db[AUDIT_LOGS_COLLECTION].distinct("action"))


async def list_audit_logs(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str | None = None,
    actor: str | None = None,
    action: str | None = None,
    result: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    document_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    clauses: list[dict[str, Any]] = []
    if actor_id:
        clauses.append({"actor_id": _id_filter(actor_id)})
    if actor:
        clauses.append({"actor_id": {"$in": await _actor_search_ids(db, actor)}})
    if action:
        clauses.append({"action": action})
    if result:
        clauses.append({"result": result})
    if target_type:
        clauses.append({"target_type": target_type})
    if target_id:
        clauses.append({"target_id": _id_filter(target_id)})
    if document_id:
        clauses.append({"target_id": {"$in": await _document_target_ids(db, document_id)}})
    if date_from or date_to:
        created_range: dict[str, Any] = {}
        if date_from:
            created_range["$gte"] = date_from
        if date_to:
            created_range["$lte"] = date_to
        clauses.append({"created_at": created_range})
    query: dict[str, Any] = {"$and": clauses} if clauses else {}

    skip = (page - 1) * limit
    cursor = (
        db[AUDIT_LOGS_COLLECTION].find(query).sort("created_at", -1).skip(skip).limit(limit)
    )
    items = [doc async for doc in cursor]
    total = await db[AUDIT_LOGS_COLLECTION].count_documents(query)
    return items, total
