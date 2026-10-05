"""verify module Pydantic schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

VerificationResultLiteral = Literal[
    "VERIFIED",
    "MISMATCH",
    "NOT_ANCHORED",
    "ANCHOR_MISSING",
    "FILE_MISSING",
    "CHAIN_UNREACHABLE",
]


class VerifyResponse(BaseModel):
    result: VerificationResultLiteral
    recomputed: str | None  # None only for FILE_MISSING (there were no bytes to hash)
    stored: str
    onchain: str | None
    tx_hash: str | None
    etherscan_url: str | None
    # A fixed code (e.g. CHAIN_TIMEOUT, RPC_UNREACHABLE, CONTRACT_NOT_DEPLOYED), never error text.
    reason: str | None = None


class VerificationRecordOut(BaseModel):
    id: str
    version_id: str
    requested_by: str
    recomputed_hash: str | None
    stored_hash: str
    onchain_hash: str | None
    result: VerificationResultLiteral
    created_at: datetime
    reason: str | None = None


class VerificationHistoryOut(BaseModel):
    items: list[VerificationRecordOut]
