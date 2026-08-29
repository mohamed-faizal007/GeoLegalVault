"""blockchain module Mongo collection."""

from enum import StrEnum

BLOCKCHAIN_ANCHORS_COLLECTION = "blockchain_anchors"

NETWORK = "sepolia"
ETHERSCAN_TX_BASE = "https://sepolia.etherscan.io/tx"


class AnchorStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
