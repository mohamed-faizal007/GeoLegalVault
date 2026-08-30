"""verify module Mongo collection — `verification_records` is append-only:
every call to POST /verify/{version_id} inserts one row, win or lose. There
is no update/delete path (Phase 8's audit_logs gets the same treatment).
"""

from enum import StrEnum

VERIFICATION_RECORDS_COLLECTION = "verification_records"


class VerificationResult(StrEnum):
    VERIFIED = "VERIFIED"
    MISMATCH = "MISMATCH"
    NOT_ANCHORED = "NOT_ANCHORED"
