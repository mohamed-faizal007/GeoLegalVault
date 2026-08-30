"""reports module Pydantic schemas — the GET /reports/summary shape."""

from pydantic import BaseModel


class StatusCount(BaseModel):
    status: str
    count: int


class DocTypeCount(BaseModel):
    doc_type: str
    count: int


class AnchoringStats(BaseModel):
    pending: int
    confirmed: int
    failed: int
    success_rate: float  # confirmed / (confirmed + failed); 0.0 if neither exists yet


class VerificationStats(BaseModel):
    verified: int
    mismatch: int
    not_anchored: int
    window_days: int


class ReportsSummary(BaseModel):
    documents_by_status: list[StatusCount]
    documents_by_doc_type: list[DocTypeCount]
    anchoring: AnchoringStats
    verifications_recent: VerificationStats
    geofence_denied_count: int
