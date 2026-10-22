"""Read-only 'Supplementary view' line builders. Real data, secrets projected out. Nothing here writes."""
import json

from bson import ObjectId

from common import bucket, db, storage_client


def names() -> dict:
    return {u["_id"]: u.get("name") or u["email"] for u in db().users.find({}, {"name": 1, "email": 1})}


def short(v, n=64):
    s = str(v)
    return s if len(s) <= n else s[: n - 1] + "…"


def storage_head(key: str) -> dict:
    try:
        h = storage_client().head_object(Bucket=bucket(), Key=key)
        return {"key": key, "size_bytes": h["ContentLength"], "content_type": h["ContentType"]}
    except Exception as e:  # noqa: BLE001
        return {"key": key, "error": type(e).__name__}


def versions(document_id: str) -> list[dict]:
    return list(db().document_versions.find({"document_id": ObjectId(document_id)}).sort("version_no", 1))


def doc_version_lines(document_id: str) -> list[str]:
    """Document row and version row(s), cropped to the lines that matter."""
    d = db()
    doc = d.documents.find_one({"_id": ObjectId(document_id)})
    nm = names()
    out = ["documents (one row)",
           f"  title                {doc['title']}",
           f"  classification       {doc['classification']}      status  {doc['status']}",
           f"  owner                {nm.get(doc['owner_id'], '?')}",
           ""]
    for v in versions(document_id):
        out += [f"document_versions  version_no = {v['version_no']}",
                f"  sha256             {v['sha256']}",
                f"  prev_version_hash  {v.get('prev_version_hash')}",
                f"  size_bytes         {v['size_bytes']}      mime  {v['mime']}      status  {v['status']}",
                f"  storage_key        {v['storage_key']}", ""]
    return out


def bucket_lines(document_id: str) -> list[str]:
    resp = storage_client().list_objects_v2(Bucket=bucket(), Prefix=f"docs/{document_id}/")
    out = ["private bucket, objects under docs/<documentId>/   (read-only listing)"]
    for o in resp.get("Contents", []):
        out.append(f"  {o['Key']}   {o['Size']} bytes")
    if len(out) == 1:
        out.append("  (none)")
    return out


def anchor_lines(document_id: str) -> list[str]:
    out = ["blockchain_anchors (one row per version)"]
    for a in db().blockchain_anchors.find({"document_id": ObjectId(document_id)}).sort("created_at", 1):
        out += [f"  status {a['status']}   network {a.get('network')}   block {a.get('block_number')}",
                f"  tx_hash   {a.get('tx_hash')}",
                f"  sha256    {a['sha256']}"]
    return out


def audit_lines(document_id: str | None = None, actions: list[str] | None = None, limit: int = 12,
                since=None) -> list[str]:
    d = db()
    nm = names()
    q: dict = {}
    if document_id:
        oid = ObjectId(document_id)
        vids = [v["_id"] for v in d.document_versions.find({"document_id": oid}, {"_id": 1})]
        q["$or"] = [{"target_id": oid}, {"target_id": {"$in": vids}}]
    if actions:
        q["action"] = {"$in": actions}
    if since is not None:
        q["created_at"] = {"$gte": since}
    rows = list(d.audit_logs.find(q).sort("created_at", -1).limit(limit))
    rows.reverse()
    out = ["audit_logs (oldest to newest)", f"  {'time':8}  {'action':<17}{'result':<9}{'actor':<19}meta"]
    for r in rows:
        meta = json.dumps(r.get("meta") or {}, default=str, separators=(",", ":"))
        if r.get("location"):
            meta = f"location={r['location']} " + meta
        out.append(f"  {r['created_at']:%H:%M:%S}  {r['action']:<17}{r['result']:<9}{short(nm.get(r.get('actor_id'), '-'), 18):<19}{short(meta, 70)}")
    return out
