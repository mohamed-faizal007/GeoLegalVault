"""audit module Pydantic schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: str
    actor_id: str | None
    action: str
    target_type: str
    target_id: str | None
    result: str
    ip: str | None = None
    location: dict[str, Any] | None = None
    meta: dict[str, Any] = {}
    created_at: datetime


class AuditLogListOut(BaseModel):
    items: list[AuditLogOut]
    page: int
    limit: int
    total: int
