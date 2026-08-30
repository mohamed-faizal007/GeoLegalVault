"""documents module Pydantic schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: str
    title: str
    doc_type: str
    classification: str
    owner_id: str
    status: str
    current_version_id: str | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    retention_until: datetime | None = None
    integrity_flag: str | None = None


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    page: int
    limit: int
    total: int


class UploadResponse(BaseModel):
    document_id: str
    version_id: str
    sha256: str
    status: str


class DownloadResponse(BaseModel):
    url: str
    expires_in_sec: int


class ReviewDecision(BaseModel):
    decision: Literal["approve", "changes_requested"]
    comment: str | None = None


class AmendRequest(BaseModel):
    reason: str = Field(min_length=1)


class TransitionResponse(BaseModel):
    document_id: str
    status: str
    version_id: str | None = None
    anchor_status: str | None = None
    tx_hash: str | None = None


class DocumentSearchParams(BaseModel):
    query: str | None = None
    status: str | None = None
    doc_type: str | None = None
    owner_id: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
