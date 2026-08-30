import { http } from "./http";

export interface AuditLogOut {
  id: string;
  actor_id: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  result: string;
  ip: string | null;
  location: { type: string; coordinates: number[] } | null;
  meta: Record<string, unknown>;
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
