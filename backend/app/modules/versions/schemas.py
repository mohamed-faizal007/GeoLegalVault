"""versions module Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class VersionOut(BaseModel):
    id: str
    document_id: str
    version_no: int
    sha256: str
    prev_version_hash: str | None
    storage_key: str
    size_bytes: int
    mime: str
    status: str
    uploaded_by: str
    uploaded_at: datetime
    anchored: bool
    anchor_id: str | None = None


class VersionListOut(BaseModel):
    items: list[VersionOut]
