"""Copy every object from one S3-compatible endpoint to another (D-034 follow-up).

Purpose: after MinIO was replaced by RustFS, the dev Mongo still references
objects that live in the old MinIO volume. This copies them across so those
documents download and verify again.

Safe by construction:
  * the SOURCE is only listed and read (GET); nothing is ever written to or
    deleted from it;
  * the DESTINATION is never overwritten: an existing key with identical
    bytes is skipped, an existing key with DIFFERENT bytes is reported as a
    CONFLICT and left alone (Guardrail #7: bytes behind a recorded hash must
    not change);
  * every copied object is read back from the destination and its SHA-256
    compared with the source before it counts as copied;
  * nothing is deleted anywhere.

Credentials: both ends use STORAGE_ACCESS_KEY / STORAGE_SECRET_KEY from the
environment/.env (docker-compose gives the old MinIO and the new RustFS the same
pair). Override the source's with --source-access-key/--source-secret-key.

Usage (from the repo root, backend venv active):
    python scripts/migrate_storage.py --source-endpoint http://localhost:9100 --dry-run
    python scripts/migrate_storage.py --source-endpoint http://localhost:9100

Exit code is non-zero if any object conflicted, failed, or a version row in
Mongo points at a key the source does not have.
"""

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import boto3  # noqa: E402
from botocore.client import BaseClient, Config  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.modules.versions.models import DOCUMENT_VERSIONS_COLLECTION  # noqa: E402


def _client(endpoint: str, access_key: str, secret_key: str, region: str) -> BaseClient:
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=Config(signature_version="s3v4"),
    )


def _list_keys(client: BaseClient, bucket: str) -> dict[str, int]:
    keys: dict[str, int] = {}
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            keys[obj["Key"]] = obj["Size"]
    return keys


def _read(client: BaseClient, bucket: str, key: str) -> tuple[bytes, str]:
    response = client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read(), response.get("ContentType", "application/octet-stream")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _mongo_keys() -> set[str] | None:
    """storage_keys of every version row, or None if Mongo is unreachable."""
    try:
        from pymongo import MongoClient

        settings = get_settings()
        client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=2000)
        rows = client[settings.MONGODB_DB][DOCUMENT_VERSIONS_COLLECTION].find({}, {"storage_key": 1})
        return {row["storage_key"] for row in rows}
    except Exception as exc:  # noqa: BLE001 — a diagnostic cross-check, never fatal
        print(f"WARNING: could not read Mongo for the cross-check ({type(exc).__name__}).")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source-endpoint", required=True)
    parser.add_argument("--dest-endpoint", help="default: STORAGE_ENDPOINT")
    parser.add_argument("--source-access-key")
    parser.add_argument("--source-secret-key")
    parser.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    parser.add_argument(
        "--only-referenced",
        action="store_true",
        help="copy only objects some document_versions row points at (skips test/probe leftovers)",
    )
    args = parser.parse_args()

    settings = get_settings()
    bucket = settings.STORAGE_BUCKET
    dest_endpoint = args.dest_endpoint or settings.STORAGE_ENDPOINT
    if args.source_endpoint.rstrip("/") == dest_endpoint.rstrip("/"):
        print("Source and destination are the same endpoint — refusing.")
        return 2

    source = _client(
        args.source_endpoint,
        args.source_access_key or settings.STORAGE_ACCESS_KEY,
        args.source_secret_key or settings.STORAGE_SECRET_KEY,
        settings.STORAGE_REGION,
    )
    dest = _client(
        dest_endpoint, settings.STORAGE_ACCESS_KEY, settings.STORAGE_SECRET_KEY, settings.STORAGE_REGION
    )

    referenced = _mongo_keys()
    if args.only_referenced and referenced is None:
        print("--only-referenced needs Mongo, which is unreachable — refusing.")
        return 2

    source_keys = _list_keys(source, bucket)
    dest_keys = _list_keys(dest, bucket)
    to_copy = (
        {k: v for k, v in source_keys.items() if k in referenced}
        if args.only_referenced
        else source_keys
    )
    print(f"source {args.source_endpoint}: {len(source_keys)} objects; "
          f"destination {dest_endpoint}: {len(dest_keys)} objects (bucket {bucket})")

    copied = skipped = 0
    conflicts: list[str] = []
    failures: list[str] = []
    for key in sorted(to_copy):
        try:
            data, content_type = _read(source, bucket, key)
            digest = _sha(data)
            if key in dest_keys:
                existing, _ = _read(dest, bucket, key)
                if _sha(existing) == digest:
                    skipped += 1
                else:
                    conflicts.append(key)
                    print(f"CONFLICT (different bytes already at destination, left untouched): {key}")
                continue
            if args.dry_run:
                print(f"would copy {key} ({len(data)} bytes)")
                copied += 1
                continue
            dest.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
            back, _ = _read(dest, bucket, key)
            if _sha(back) != digest:
                failures.append(key)
                print(f"FAILED read-back check: {key}")
                continue
            copied += 1
        except ClientError as exc:
            failures.append(key)
            print(f"FAILED {key}: {exc.response.get('Error', {}).get('Code')}")

    verb = "would copy" if args.dry_run else "copied"
    print(f"{verb} {copied}, already identical {skipped}, conflicts {len(conflicts)}, failures {len(failures)}")

    missing: list[str] = []
    if referenced is not None:
        missing = sorted(referenced - set(source_keys) - set(dest_keys))
        unreferenced = len(set(source_keys) - referenced)
        print(f"Mongo cross-check: {len(referenced)} version rows; "
              f"{len(missing)} point at a key found in neither store; "
              f"{unreferenced} source objects are not referenced by any version row.")
        for key in missing:
            print(f"  MISSING EVERYWHERE: {key}")

    return 1 if (conflicts or failures or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
