import { http } from "./http";

export type VerificationResult = "VERIFIED" | "MISMATCH" | "NOT_ANCHORED";

export interface VerifyResponse {
  result: VerificationResult;
  recomputed: string;
  stored: string;
  onchain: string | null;
  tx_hash: string | null;
  etherscan_url: string | null;
}

export interface VerificationRecordOut {
  id: string;
  version_id: string;
  requested_by: string;
  recomputed_hash: string;
  stored_hash: string;
  onchain_hash: string | null;
  result: VerificationResult;
  created_at: string;
}

export interface VerificationHistoryOut {
  items: VerificationRecordOut[];
}

export function runVerify(versionId: string): Promise<VerifyResponse> {
  return http.post<VerifyResponse>(`/verify/${versionId}`);
}

export function getVerifyHistory(versionId: string): Promise<VerificationHistoryOut> {
  return http.get<VerificationHistoryOut>(`/verify/${versionId}/history`);
}
