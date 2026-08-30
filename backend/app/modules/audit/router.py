"""audit module router — read-only, Auditor/Administrator only (Plan Part 3:
Auditor is read-only everywhere but can view all audit logs; Administrator
also holds audit:view). There is deliberately no POST/PATCH/DELETE here:
the only writer is `service.record()`, called from inside other modules."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.db import get_db
from app.core.rbac import AUDIT_VIEW, require
from app.modules.audit import service
from app.modules.audit.schemas import AuditLogListOut

router = APIRouter(prefix="/audit", tags=["audit"])

_require_audit_view = require(AUDIT_VIEW)


@router.get("", response_model=AuditLogListOut)
async def list_audit_logs(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _actor: Annotated[dict, Depends(_require_audit_view)],
    actor_id: str | None = None,
    action: str | None = None,
    result: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AuditLogListOut:
    items, total = await service.list_audit_logs(
        db,
        actor_id=actor_id,
        action=action,
        result=result,
        target_type=target_type,
        target_id=target_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )
    return AuditLogListOut(
        items=[service.to_out(doc) for doc in items], page=page, limit=limit, total=total
    )
