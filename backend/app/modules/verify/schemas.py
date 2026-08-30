"""verify module Pydantic schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

VerificationResultLiteral = Literal["VERIFIED", "MISMATCH", "NOT_ANCHORED"]


class VerifyResponse(BaseModel):
    result: VerificationResultLiteral
    recomputed: str
    stored: str
    onchain: str | None
    tx_hash: str | None
    etherscan_url: str | None


class VerificationRecordOut(BaseModel):
    id: str
    version_id: str
    requested_by: str
    recomputed_hash: str
    stored_hash: str
    onchain_hash: str | None
    result: VerificationResultLiteral
    created_at: datetime


class VerificationHistoryOut(BaseModel):
    items: list[VerificationRecordOut]
