"""reports module router — read-only aggregation endpoint for the admin
dashboard. Reuses audit:view (Administrator + Auditor) rather than inventing
a new permission string not in the Plan Part 3 matrix."""

from typing import Annotated

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.db import get_db
from app.core.rbac import AUDIT_VIEW, require
from app.modules.reports import service
from app.modules.reports.schemas import ReportsSummary

router = APIRouter(prefix="/reports", tags=["reports"])

_require_reports_view = require(AUDIT_VIEW)


@router.get("/summary", response_model=ReportsSummary)
async def get_summary(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _actor: Annotated[dict, Depends(_require_reports_view)],
) -> ReportsSummary:
    return await service.get_summary(db)
