import { http } from "./http";

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
