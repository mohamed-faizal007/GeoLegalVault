"""Seed script — Phase 1 provisions the first admin user.

Later phases extend this to seed geofences and sample documents.

Usage (run from repo root, with the backend's venv active or MONGODB_URI
pointed at a reachable Mongo):
    python scripts/seed.py --email admin@example.com --password "Str0ngPass!"
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.db import close_client, ensure_indexes, get_database  # noqa: E402
from app.modules.users.service import EmailAlreadyExists, create_admin  # noqa: E402


async def _run(email: str, password: str, name: str) -> None:
    db = get_database()
    await ensure_indexes()
    try:
        user = await create_admin(db, email=email, password=password, name=name)
    except EmailAlreadyExists:
        print(f"Admin '{email}' already exists — skipping.")
    else:
        print(f"Created admin user: {user.email} ({user.id})")
    finally:
        await close_client()


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision the first admin user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default="Administrator")
    args = parser.parse_args()
    asyncio.run(_run(args.email, args.password, args.name))


if __name__ == "__main__":
    main()
