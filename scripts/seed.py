"""Seed script.

Phase 1: provision a single user (default role ADMINISTRATOR).
Phase 3: --role lets that user be any of the 5 roles; --demo seeds one user
per role plus a sample HQ geofence and prints a known inside/outside test
coordinate, for exercising geofence enforcement across roles.

Usage (run from repo root, with the backend's venv active or MONGODB_URI
pointed at a reachable Mongo):
    python scripts/seed.py --email admin@example.com --password "Str0ngPass!"
    python scripts/seed.py --email legal@example.com --password "Str0ngPass!" --role LEGAL_OFFICER
    python scripts/seed.py --demo
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.db import close_client, ensure_indexes, get_database  # noqa: E402
from app.modules.geofences.models import GEOFENCES_COLLECTION  # noqa: E402
from app.modules.geofences.schemas import GeofenceCreate, GeoJSONPolygon  # noqa: E402
from app.modules.geofences.service import create_geofence  # noqa: E402
from app.modules.users.models import Role  # noqa: E402
from app.modules.users.schemas import UserCreate  # noqa: E402
from app.modules.users.service import create_user, get_user_by_email  # noqa: E402

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
    args = parser.parse_args()

    if args.demo:
        asyncio.run(_run_demo())
        return

    if not args.email or not args.password:
        parser.error("--email and --password are required unless --demo is given")

    asyncio.run(_run_single(args.email, args.password, args.name, Role(args.role)))


if __name__ == "__main__":
    main()
