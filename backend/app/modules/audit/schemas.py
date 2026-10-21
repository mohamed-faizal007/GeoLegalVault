"""audit module Pydantic schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: str
    actor_id: str | None
    # Who that is, resolved when the page is read (D-054): the user's name (else their email), or
    # None when the stored actor is not a user that still exists. `actor_id` is always kept.
    actor_label: str | None = None
    actor_email: str | None = None
    action: str
    target_type: str
    target_id: str | None
    # A readable name for the target: a user's name, or a document's title (with the version number
    # for a version) only if the viewer's clearance reaches the document (D-051). Otherwise None.
    target_label: str | None = None
    result: str
    ip: str | None = None
    location: dict[str, Any] | None = None
    meta: dict[str, Any] = {}
    # True when `meta` was withheld because the target is above the viewer's clearance (D-051).
    redacted: bool = False
    created_at: datetime


class AuditLogListOut(BaseModel):
    items: list[AuditLogOut]
    page: int
    limit: int
    total: int


class AuditActionsOut(BaseModel):
    actions: list[str]
