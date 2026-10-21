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
from app.modules.audit.schemas import AuditActionsOut, AuditLogListOut

router = APIRouter(prefix="/audit", tags=["audit"])

_require_audit_view = require(AUDIT_VIEW)


# Filter values are bounded and shaped here so nothing unbounded reaches a query (D-055).
_Id = Annotated[str | None, Query(max_length=100)]
_Name = Annotated[str | None, Query(max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")]
_ObjectIdText = Annotated[str | None, Query(pattern=r"^[0-9a-fA-F]{24}$")]


@router.get("/actions", response_model=AuditActionsOut)
async def list_audit_actions(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _actor: Annotated[dict, Depends(_require_audit_view)],
) -> AuditActionsOut:
    """The action names that exist in the log, so the filter offers real values."""
    return AuditActionsOut(actions=await service.list_actions(db))


@router.get("", response_model=AuditLogListOut)
async def list_audit_logs(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    actor: Annotated[dict, Depends(_require_audit_view)],
    actor_id: _Id = None,
    actor_search: Annotated[str | None, Query(alias="actor", min_length=2, max_length=100)] = None,
    action: _Name = None,
    result: _Name = None,
    target_type: _Name = None,
    target_id: _Id = None,
    document_id: _ObjectIdText = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AuditLogListOut:
    items, total = await service.list_audit_logs(
        db,
        actor_id=actor_id,
        actor=actor_search,
        action=action,
        result=result,
        target_type=target_type,
        target_id=target_id,
        document_id=document_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )
    hidden = await service.hidden_row_ids(db, actor, items)
    users, target_labels = await service.resolve_labels(db, actor, items)
    return AuditLogListOut(
        items=[
            service.to_out(
                doc,
                redacted=doc["_id"] in hidden,
                users=users,
                target_label=target_labels.get(doc["_id"]),
            )
            for doc in items
        ],
        page=page,
        limit=limit,
        total=total,
    )
