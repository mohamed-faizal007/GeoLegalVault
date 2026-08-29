"""blockchain module Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


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
