"""blockchain module Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OnchainAnchor(BaseModel):
    hash: str
    event_type: int
    ts: int
    exists: bool


class AnchorOut(BaseModel):
    id: str
    document_id: str
    version_id: str
    sha256: str
    event_type: int
    tx_hash: str | None
    block_number: int | None
    contract_address: str
    network: str
    status: str
    created_at: datetime
    confirmed_at: datetime | None
    etherscan_url: str | None
    onchain: OnchainAnchor | None = None
    error: str | None = None


class AnchorAttentionItem(BaseModel):
    """One document whose anchor needs attention (D-041). No hash, key, URL or tx detail."""

    document_id: str
    title: str
    version_no: int
    state: str  # RETRYING | AWAITING_CONFIRMATION | PERMANENT_FAILURE | NEEDS_ADMIN_RETRY
    last_error: str | None  # a fixed code from anchor_errors, never raw text
    attempts: int
    next_attempt_at: datetime | None
    stuck_since: datetime
    can_retry: bool  # whether *the caller* may ask for a re-drive


class AnchorAttentionOut(BaseModel):
    items: list[AnchorAttentionItem]
    total: int


class AnchorRetryRequest(BaseModel):
    """Nothing here names a hash, version, tx or address: a re-drive only re-queues what the
    system already owes, from the DB version row."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=10, max_length=1000)


class AnchorRetryOut(BaseModel):
    document_id: str
    state: str
    next_attempt_at: datetime | None
