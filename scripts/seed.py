"""Seed script.

Phase 1: provision a single user (default role ADMINISTRATOR).
Phase 3: --role lets that user be any of the 5 roles; --demo seeds one user
per role plus a sample HQ geofence and prints a known inside/outside test
coordinate, for exercising geofence enforcement across roles.
Phase 12: --seed-documents populates the synthetic document corpus (Plan
Part 21) used by DEMO_SCRIPT.md — ~30-50 placeholder documents spread across
the lifecycle states, five taken through a real V1->V2 amendment, and five
deliberately tampered in storage after anchoring so the Verify page has
ready-made MISMATCH cases. Requires --demo to have been run first, and
requires real blockchain config (SEPOLIA_RPC_URL / SERVICE_WALLET_PRIVATE_KEY
/ CONTRACT_ADDRESS) for the amendment/tamper cases to be meaningful — without
it, approvals stay APPROVED (pending anchor) instead of reaching ACTIVE.

Usage (run from repo root, with the backend's venv active or MONGODB_URI
pointed at a reachable Mongo):
    python scripts/seed.py --email admin@example.com --password "Str0ngPass!"
    python scripts/seed.py --email legal@example.com --password "Str0ngPass!" --role LEGAL_OFFICER
    python scripts/seed.py --demo
    python scripts/seed.py --seed-documents
    python scripts/seed.py --seed-documents --count 40
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.db import close_client, ensure_indexes, get_database  # noqa: E402
from app.modules.documents import service as documents_service  # noqa: E402
from app.modules.documents import workflow as documents_workflow  # noqa: E402
from app.modules.documents.models import DOCUMENTS_COLLECTION, DocumentStatus  # noqa: E402
from app.modules.geofences.models import GEOFENCES_COLLECTION  # noqa: E402
from app.modules.geofences.schemas import GeofenceCreate, GeoJSONPolygon  # noqa: E402
from app.modules.geofences.service import create_geofence  # noqa: E402
from app.modules.users.models import Role  # noqa: E402
from app.modules.users.schemas import UserCreate  # noqa: E402
from app.modules.users.service import create_user, get_user_by_email  # noqa: E402
from app.modules.versions import service as versions_service  # noqa: E402
from app.services import storage  # noqa: E402

DEMO_PASSWORD = "Demo@Pass123!"
DEMO_GEOFENCE_NAME = "HQ Campus (demo)"

# Same HQ campus box used as the worked example in the project plan (Part 10).
HQ_RING = [
    [78.14, 11.66],
    [78.16, 11.66],
    [78.16, 11.68],
    [78.14, 11.68],
    [78.14, 11.66],
]
HQ_INSIDE_POINT = {"lat": 11.67, "lng": 78.15}
HQ_OUTSIDE_POINT = {"lat": 11.00, "lng": 77.00}  # ~100km away — clearly outside


async def _create_user_if_absent(
    db, *, email: str, password: str, name: str, role: Role, geofence_ids: list[str] | None = None
):
    if await get_user_by_email(db, email) is not None:
        print(f"User '{email}' already exists — skipping.")
        return None
    user = await create_user(
        db,
        UserCreate(
            email=email,
            password=password,
            name=name,
            role=role,
            assigned_geofence_ids=geofence_ids or [],
        ),
    )
    print(f"Created {role.value} user: {user.email} ({user.id})")
    return user


async def _create_hq_geofence_if_absent(db) -> str:
    existing = await db[GEOFENCES_COLLECTION].find_one({"name": DEMO_GEOFENCE_NAME})
    if existing is not None:
        print(f"Geofence '{DEMO_GEOFENCE_NAME}' already exists — reusing it.")
        return str(existing["_id"])

    geofence = await create_geofence(
        db,
        GeofenceCreate(name=DEMO_GEOFENCE_NAME, region=GeoJSONPolygon(coordinates=[HQ_RING])),
    )
    print(f"Created demo geofence: {geofence.name} ({geofence.id})")
    return geofence.id


async def _run_single(email: str, password: str, name: str, role: Role) -> None:
    db = get_database()
    await ensure_indexes()
    try:
        await _create_user_if_absent(db, email=email, password=password, name=name, role=role)
    finally:
        await close_client()


async def _run_demo() -> None:
    db = get_database()
    await ensure_indexes()
    try:
        geofence_id = await _create_hq_geofence_if_absent(db)
        for role in Role:
            email = f"{role.value.lower()}@geolegalvault.demo"
            await _create_user_if_absent(
                db,
                email=email,
                password=DEMO_PASSWORD,
                name=role.value.title(),
                role=role,
                geofence_ids=[geofence_id],
            )

        print()
        print(f"Demo users (all password: {DEMO_PASSWORD}):")
        for role in Role:
            print(f"  {role.value:<20} {role.value.lower()}@geolegalvault.demo")
        print()
        print(f"HQ geofence: '{DEMO_GEOFENCE_NAME}' ({geofence_id})")
        print(f"  inside point:  lat={HQ_INSIDE_POINT['lat']} lng={HQ_INSIDE_POINT['lng']}")
        print(f"  outside point: lat={HQ_OUTSIDE_POINT['lat']} lng={HQ_OUTSIDE_POINT['lng']}")
    finally:
        await close_client()


# --- Phase 12: synthetic document corpus (Plan Part 21) -------------------

DOC_TYPES = ["CONTRACT", "NDA", "MOU", "POLICY_MEMO", "NOTICE"]
CLASSIFICATIONS = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]
FAKE_PARTIES = [
    "Acme Corp",
    "Northwind Traders",
    "Contoso Industries",
    "Globex LLC",
    "Initech Systems",
    "Umbrella Logistics",
    "Stark Compliance Ltd",
    "Wayne Records Office",
]
FAKE_OFFICERS = ["Officer A. Rao", "Officer S. Iyer", "Officer K. Menon", "Officer P. Nair"]

SYNTHETIC_TAG = "synthetic"


def _document_spec(i: int) -> dict:
    doc_type = DOC_TYPES[i % len(DOC_TYPES)]
    classification = CLASSIFICATIONS[i % len(CLASSIFICATIONS)]
    party = FAKE_PARTIES[i % len(FAKE_PARTIES)]
    officer = FAKE_OFFICERS[i % len(FAKE_OFFICERS)]
    title = f"{doc_type.replace('_', ' ').title()} — {party} ({i + 1:03d})"
    tags = [doc_type.lower(), classification.lower(), SYNTHETIC_TAG]
    body = (
        "GeoLegalVault Synthetic Document\n"
        f"Type: {doc_type}\n"
        f"Classification: {classification}\n"
        f"Parties: GeoLegalVault Demo Org and {party}\n"
        f"Signing Officer: {officer}\n"
        f"Reference: DOC-{i + 1:03d}-V1\n\n"
        "This is placeholder text generated for demonstration and testing "
        "purposes only. It does not represent a real legal agreement, and "
        "no confidential information is contained in this file.\n"
    ).encode("utf-8")
    return {"title": title, "doc_type": doc_type, "classification": classification, "tags": tags, "body": body}


async def _run_documents(count: int) -> None:
    db = get_database()
    await ensure_indexes()
    try:
        existing = await db[DOCUMENTS_COLLECTION].count_documents({"tags": SYNTHETIC_TAG})
        if existing >= count:
            print(
                f"{existing} synthetic documents already exist (>= requested {count}) — "
                "skipping to avoid duplicate accumulation. Drop the 'documents'/'document_versions' "
                "collections (or lower --count) to reseed."
            )
            return

        uploader = await get_user_by_email(db, f"{Role.AUTHORIZED_STAFF.value.lower()}@geolegalvault.demo")
        reviewer = await get_user_by_email(db, f"{Role.REVIEWING_OFFICER.value.lower()}@geolegalvault.demo")
        approver = await get_user_by_email(db, f"{Role.LEGAL_OFFICER.value.lower()}@geolegalvault.demo")
        if not uploader or not reviewer or not approver:
            print("Demo users not found — run 'python scripts/seed.py --demo' first.")
            return

        active_docs: list[dict] = []
        stage_counts = {
            "DRAFT": 0,
            "SUBMITTED": 0,
            "CHANGES_REQUESTED->DRAFT": 0,
            "PENDING_APPROVAL": 0,
            "ADVANCED (approve attempted)": 0,
        }

        for i in range(count):
            spec = _document_spec(i)
            result = await documents_service.create_document_with_v1(
                db,
                title=spec["title"],
                doc_type=spec["doc_type"],
                classification=spec["classification"],
                tags=spec["tags"],
                owner_id=uploader["_id"],
                data=spec["body"],
                content_type="text/plain",
            )
            document = result["document"]

            # Deterministic 10-way bucket -> a realistic spread across the
            # lifecycle states so search/filter/report demos have variety.
            bucket = i % 10
            if bucket < 2:
                stage_counts["DRAFT"] += 1
                continue

            document = await documents_workflow.submit(db, document=document, actor=uploader)
            if bucket < 3:
                stage_counts["SUBMITTED"] += 1
                continue

            if bucket == 3:
                await documents_workflow.review(
                    db,
                    document=document,
                    actor=reviewer,
                    decision="changes_requested",
                    comment="Please add a signature block before resubmitting.",
                )
                stage_counts["CHANGES_REQUESTED->DRAFT"] += 1
                continue

            document = await documents_workflow.review(
                db, document=document, actor=reviewer, decision="approve", comment=None
            )
            if bucket == 4:
                stage_counts["PENDING_APPROVAL"] += 1
                continue

            approve_result = await documents_workflow.approve(db, document=document, actor=approver)
            document = approve_result["document"]
            stage_counts["ADVANCED (approve attempted)"] += 1
            if document["status"] in (
                DocumentStatus.ACTIVE.value,
                DocumentStatus.BLOCKCHAIN_ANCHORED.value,
                DocumentStatus.APPROVED.value,
            ):
                active_docs.append(document)

        print()
        print("Document pipeline stage distribution:")
        for stage, n in stage_counts.items():
            print(f"  {stage:<28} {n}")

        # Only fully-ACTIVE (i.e. actually anchored+confirmed) documents make
        # good amendment/tamper demo cases — MISMATCH/VERIFIED only mean
        # anything once there's a real on-chain hash to compare against.
        anchored = [d for d in active_docs if d["status"] == DocumentStatus.ACTIVE.value]
        amendment_targets = anchored[:5]
        tamper_targets = anchored[5:10]

        print()
        print(f"Amending {len(amendment_targets)} document(s) to V2 ...")
        for document in amendment_targets:
            await documents_workflow.request_amendment(
                db, document=document, actor=uploader, reason="Corrected clause 4.2 wording."
            )
            fresh = await documents_service.get_document_by_id(db, str(document["_id"]))
            new_body = (
                "GeoLegalVault Synthetic Document (Amended)\n"
                f"Title: {document['title']}\n"
                "This is version 2, created through the amendment workflow to "
                "correct clause 4.2 wording. Placeholder text only.\n"
            ).encode("utf-8")
            next_version_result = await documents_service.create_next_version(
                db,
                document=fresh,
                actor_id=uploader["_id"],
                data=new_body,
                content_type="text/plain",
            )
            v2_document = next_version_result["document"]
            v2_document = await documents_workflow.submit(db, document=v2_document, actor=uploader)
            v2_document = await documents_workflow.review(
                db, document=v2_document, actor=reviewer, decision="approve", comment=None
            )
            v2_result = await documents_workflow.approve(db, document=v2_document, actor=approver)
            print(f"  {document['title']} -> V2 status={v2_result['document']['status']}")

        print()
        print(f"Tampering {len(tamper_targets)} document(s) for the live Verify demo ...")
        for document in tamper_targets:
            version = await versions_service.get_latest_version(db, document["_id"])
            tampered = bytearray(storage.get_object(version["storage_key"]))
            tampered[0] = (tampered[0] + 1) % 256  # a controlled 1-byte change
            storage.put_object(bytes(tampered), version["storage_key"], version["mime"])
            print(f"  {document['title']} (version {version['version_no']}) — blob tampered in storage")

        print()
        print(f"Seeded {count} synthetic documents.")
        if len(anchored) < 10:
            print(
                "WARNING: fewer than 10 documents reached ACTIVE — this usually means "
                "blockchain anchoring is not configured (SEPOLIA_RPC_URL / "
                "SERVICE_WALLET_PRIVATE_KEY / CONTRACT_ADDRESS are still placeholders). "
                "The amendment/tamper demo cases need real anchoring to be meaningful — "
                "configure the chain and re-run with --seed-documents --count "
                f"{count + 1} (a higher count forces a fresh pass past the "
                "already-seeded guard)."
            )
    finally:
        await close_client()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed a user, or (--demo) one user per role plus a sample geofence."
    )
    parser.add_argument("--email")
    parser.add_argument("--password")
    parser.add_argument("--name", default="Administrator")
    parser.add_argument(
        "--role",
        choices=[role.value for role in Role],
        default=Role.ADMINISTRATOR.value,
        help="Role for the single-user form (default: ADMINISTRATOR).",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Seed one user per role plus a sample HQ geofence and test coordinates.",
    )
    parser.add_argument(
        "--seed-documents",
        action="store_true",
        help=(
            "Seed the synthetic document corpus (Part 21): ~30-50 placeholder "
            "documents across DRAFT/SUBMITTED/.../ACTIVE, 5 taken through a "
            "V1->V2 amendment, and 5 tampered in storage post-anchor for the "
            "Verify demo. Requires --demo to have been run first."
        ),
    )
    parser.add_argument(
        "--count",
        type=int,
        default=35,
        help="Number of synthetic documents for --seed-documents (default: 35).",
    )
    args = parser.parse_args()

    if args.demo:
        asyncio.run(_run_demo())
        return

    if args.seed_documents:
        asyncio.run(_run_documents(args.count))
        return

    if not args.email or not args.password:
        parser.error("--email and --password are required unless --demo or --seed-documents is given")

    asyncio.run(_run_single(args.email, args.password, args.name, Role(args.role)))


if __name__ == "__main__":
    main()
