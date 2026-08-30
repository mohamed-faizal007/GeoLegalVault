"""blockchain module Mongo collection."""

from enum import IntEnum, StrEnum

BLOCKCHAIN_ANCHORS_COLLECTION = "blockchain_anchors"

NETWORK = "sepolia"
ETHERSCAN_TX_BASE = "https://sepolia.etherscan.io/tx"


class AnchorStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class AnchorEventType(IntEnum):
    """The on-chain contract only takes a bare uint8; this fixes the app's
    own convention for it (Plan Part 5/12). Approval is the only transition
    that anchors today — more values are added here, never renumbered, if a
    later phase anchors other event types."""

    APPROVED = 1
