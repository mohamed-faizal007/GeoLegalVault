"""documents module Mongo collection."""

from enum import StrEnum

DOCUMENTS_COLLECTION = "documents"


class DocumentStatus(StrEnum):
    """Same lifecycle vocabulary as VersionStatus — a document's status
    mirrors its current version's. Phase 4 only ever sets DRAFT on upload;
    transitions between these states arrive in Phase 6."""

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
