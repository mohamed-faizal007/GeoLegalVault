"""verify module router — the 3-way verification loop (Plan Part 6 Scenario
5). No geofence gate here: verification is a read-only integrity check, not
a sensitive lifecycle operation, and it must remain checkable from anywhere
(e.g. the exact "someone downloaded this off-site, is it still legit?" case).
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.db import get_db
from app.core.deps import CurrentUser
from app.core.rbac import AUDIT_VIEW, VERIFY_PERFORM, RBACError, has_permission
from app.modules.verify import service
from app.modules.verify.schemas import VerificationHistoryOut, VerifyResponse

router = APIRouter(prefix="/verify", tags=["verify"])


def _require_verify(user: CurrentUser) -> dict:
    if not has_permission(user["role"], VERIFY_PERFORM):
        raise RBACError("FORBIDDEN", f"Missing required permission: {VERIFY_PERFORM}")
    return user


def _require_verify_or_audit(user: CurrentUser) -> dict:
    if not (
        has_permission(user["role"], VERIFY_PERFORM) or has_permission(user["role"], AUDIT_VIEW)
    ):
        raise RBACError(
            "FORBIDDEN", f"Missing required permission: {VERIFY_PERFORM} or {AUDIT_VIEW}"
        )
    return user


@router.post("/{version_id}", response_model=VerifyResponse)
async def verify_version(
    version_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(_require_verify)],
) -> VerifyResponse:
    return await service.verify_version(db, version_id=version_id, actor=user)


@router.get("/{version_id}/history", response_model=VerificationHistoryOut)
async def verify_history(
    version_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _actor: Annotated[dict, Depends(_require_verify_or_audit)],
) -> VerificationHistoryOut:
    records = await service.list_verification_history(db, version_id)
    return VerificationHistoryOut(items=[service.to_out(r) for r in records])
