"""versions module Mongo collection — document_versions is insert-only.

Only `insert_version` and the whitelisted `update_status` in service.py may
write to this collection; there is no other mutation path (Guardrail #7).
"""

from enum import StrEnum

DOCUMENT_VERSIONS_COLLECTION = "document_versions"


class VersionStatus(StrEnum):
    """The full lifecycle vocabulary (CLAUDE.md / Plan Part 5). Phase 4 only
    ever sets DRAFT on insert; the transition rules between these states
    arrive in Phase 6 — this enum just fixes the known value set."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    APPROVED = "APPROVED"
    BLOCKCHAIN_ANCHORED = "BLOCKCHAIN_ANCHORED"
    ACTIVE = "ACTIVE"
    AMENDMENT_REQUESTED = "AMENDMENT_REQUESTED"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"
