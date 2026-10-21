"""Read-only 'Supplementary view' text builders. Real data, secrets projected out. Nothing here writes."""
import json
import re

import boto3
from botocore.config import Config
from bson import ObjectId

from common import db, env


def _j(o) -> str:
    return json.dumps(o, indent=2, default=str)


def mask_user(u: dict) -> dict:
    return {k: v for k, v in u.items() if k not in ("password_hash",)}


def doc_view(document_id: str) -> str:
    d = db()
    doc = d.documents.find_one({"_id": ObjectId(document_id)})
    vers = list(d.document_versions.find({"document_id": ObjectId(document_id)}).sort("version_no", 1))
    out = ["db.documents.findOne({_id: ...})", _j(doc), "", "db.document_versions.find({document_id: ...})", _j(vers)]
    for v in vers:
        out += ["", "Storage (bucket geolegalvault-dev), HEAD object for this version's storage_key:"]
        out.append(_j(storage_head(v["storage_key"])))
    return "\n".join(out)


def storage_client():
    return boto3.client(
        "s3", endpoint_url=env("STORAGE_ENDPOINT") or "http://localhost:9000",
        aws_access_key_id=env("STORAGE_ACCESS_KEY"), aws_secret_access_key=env("STORAGE_SECRET_KEY"),
        region_name="us-east-1", config=Config(s3={"addressing_style": "path"}))


def storage_head(key: str) -> dict:
    try:
        h = storage_client().head_object(Bucket=env("STORAGE_BUCKET"), Key=key)
        return {"key": key, "size_bytes": h["ContentLength"], "content_type": h["ContentType"], "etag": h["ETag"]}
    except Exception as e:  # noqa: BLE001
        return {"key": key, "error": type(e).__name__}


def bucket_listing(document_id: str) -> str:
    resp = storage_client().list_objects_v2(Bucket=env("STORAGE_BUCKET"), Prefix=f"docs/{document_id}/")
    rows = [{"Key": o["Key"], "Size": o["Size"], "LastModified": o["LastModified"]} for o in resp.get("Contents", [])]
    return "aws s3 ls s3://geolegalvault-dev/docs/<documentId>/  (read-only listing)\n" + _j(rows)


def anchor_view(document_id: str) -> str:
    d = db()
    anchors = list(d.blockchain_anchors.find({"document_id": ObjectId(document_id)}))
    return "db.blockchain_anchors.find({document_id: ...})\n" + _j(anchors)


def audit_view(document_id: str | None = None, actions: list[str] | None = None, limit: int = 14) -> str:
    d = db()
    q: dict = {}
    if document_id:
        oid = ObjectId(document_id)
        vids = [v["_id"] for v in d.document_versions.find({"document_id": oid}, {"_id": 1})]
        q["$or"] = [{"target_id": oid}, {"target_id": {"$in": vids}}]
    if actions:
        q["action"] = {"$in": actions}
    rows = list(d.audit_logs.find(q, {"_id": 0}).sort("created_at", -1).limit(limit))
    rows.reverse()
    return "db.audit_logs.find(...).sort({created_at: -1})\n" + "\n".join(
        f"{r['created_at']:%H:%M:%S}  {r['action']:<18} {r['result']:<10} target={r['target_type']}  meta={r.get('meta')}" for r in rows)


def sha_hex(s: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", s))
