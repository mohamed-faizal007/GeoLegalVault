"""Demo helper: change one byte of a stored document, as someone with direct storage access could.

This is the "attack" in the tamper-detection demo. It bypasses the app on purpose.
Run from the repo root with the backend venv active:
    python demo/tamper.py "<document title>"
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.db import close_client, get_database  # noqa: E402
from app.modules.documents.models import DOCUMENTS_COLLECTION  # noqa: E402
from app.modules.versions import service as versions_service  # noqa: E402
from app.services import storage  # noqa: E402


async def main(title: str) -> None:
    db = get_database()
    document = await db[DOCUMENTS_COLLECTION].find_one({"title": title})
    if document is None:
        sys.exit(f"No document titled {title!r}")
    version = await versions_service.get_latest_version(db, document["_id"])
    data = bytearray(storage.get_object(version["storage_key"]))
    data[0] = (data[0] + 1) % 256
    storage.put_object(bytes(data), version["storage_key"], version["mime"])
    print(f"Changed 1 byte of V{version['version_no']} of {title!r} in storage ({version['storage_key']}).")
    await close_client()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1]))
