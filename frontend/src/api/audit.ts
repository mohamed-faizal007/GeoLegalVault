import { http } from "./http";

export interface AuditLogOut {
  id: string;
  actor_id: string | null;
  /** The actor's name (else email), or the typed email of a failed login; null if the account is gone. */
  actor_label?: string | null;
  actor_email?: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  /** A user's name, or a document's title when the viewer's clearance reaches it; else null. */
  target_label?: string | null;
  result: string;
  ip: string | null;
  location: { type: string; coordinates: number[] } | null;
  meta: Record<string, unknown>;
  /** True when `meta` was withheld: the target is a document above the viewer's clearance. */
  redacted: boolean;
  created_at: string;
}

export interface AuditLogListOut {
  items: AuditLogOut[];
  page: number;
  limit: number;
  total: number;
}

export interface AuditFilters {
  actor_id?: string;
  /** Name or email, matched on the server (at least 2 characters). */
  actor?: string;
  /** A document's whole history: the document and each of its versions. */
  document_id?: string;
  action?: string;
  result?: string;
  target_type?: string;
  target_id?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  limit?: number;
}

export function listAuditLogs(filters: AuditFilters = {}): Promise<AuditLogListOut> {
  return http.get<AuditLogListOut>("/audit", { ...filters });
}

/** The action names that exist in the log, for the filter dropdown. */
export function listAuditActions(): Promise<{ actions: string[] }> {
  return http.get<{ actions: string[] }>("/audit/actions");
}
