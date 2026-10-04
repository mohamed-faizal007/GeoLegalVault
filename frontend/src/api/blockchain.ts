import { geoHeaders, http, type GeoCoords } from "./http";

export interface OnchainAnchor {
  hash: string;
  event_type: number;
  ts: number;
  exists: boolean;
}

export interface AnchorOut {
  id: string;
  document_id: string;
  version_id: string;
  sha256: string;
  event_type: number;
  tx_hash: string | null;
  block_number: number | null;
  contract_address: string;
  network: string;
  status: string;
  created_at: string;
  confirmed_at: string | null;
  etherscan_url: string | null;
  onchain: OnchainAnchor | null;
  error: string | null;
}

export function getAnchor(versionId: string): Promise<AnchorOut> {
  return http.get<AnchorOut>(`/blockchain/anchor/${versionId}`);
}

/** Where a stuck anchor stands (D-041). Always rendered as text, never as colour alone. */
export type AnchorAttentionState =
  | "RETRYING"
  | "AWAITING_CONFIRMATION"
  | "PERMANENT_FAILURE"
  | "NEEDS_ADMIN_RETRY";

export interface AnchorAttentionItem {
  document_id: string;
  title: string;
  version_no: number;
  state: AnchorAttentionState;
  /** A fixed code from the backend, never raw error text; see lib/anchorAttention.ts. */
  last_error: string | null;
  attempts: number;
  next_attempt_at: string | null;
  stuck_since: string;
  /** Whether the server will let *this caller* ask for a re-drive. */
  can_retry: boolean;
}

export interface AnchorAttentionResponse {
  items: AnchorAttentionItem[];
  total: number;
}

export interface AnchorRetryResponse {
  document_id: string;
  state: string;
  next_attempt_at: string | null;
}

export function getAnchorAttention(): Promise<AnchorAttentionResponse> {
  return http.get<AnchorAttentionResponse>("/blockchain/anchors/attention");
}

/** Admin-only, geofenced, audited. It only re-queues: the background worker signs. */
export function retryAnchor(
  documentId: string,
  reason: string,
  coords: GeoCoords,
): Promise<AnchorRetryResponse> {
  return http.post<AnchorRetryResponse>(
    `/blockchain/anchors/${documentId}/retry`,
    { reason },
    { headers: geoHeaders(coords) },
  );
}
