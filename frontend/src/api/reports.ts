import { http } from "./http";

export interface StatusCount {
  status: string;
  count: number;
}

export interface DocTypeCount {
  doc_type: string;
  count: number;
}

export interface AnchoringStats {
  pending: number;
  confirmed: number;
  failed: number;
  success_rate: number;
}

export interface VerificationStats {
  verified: number;
  mismatch: number;
  not_anchored: number;
  window_days: number;
}

export interface ReportsSummary {
  documents_by_status: StatusCount[];
  documents_by_doc_type: DocTypeCount[];
  anchoring: AnchoringStats;
  verifications_recent: VerificationStats;
  geofence_denied_count: number;
}

export function getReportsSummary(): Promise<ReportsSummary> {
  return http.get<ReportsSummary>("/reports/summary");
}
