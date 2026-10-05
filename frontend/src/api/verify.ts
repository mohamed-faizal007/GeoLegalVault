import { http } from "./http";

export type VerificationResult =
  | "VERIFIED"
  | "MISMATCH"
  | "NOT_ANCHORED"
  | "ANCHOR_MISSING"
  | "FILE_MISSING"
  | "CHAIN_UNREACHABLE";

export interface VerifyResponse {
  result: VerificationResult;
  /** null only for FILE_MISSING (there were no bytes to hash). */
  recomputed: string | null;
  stored: string;
  onchain: string | null;
  tx_hash: string | null;
  etherscan_url: string | null;
  /** A fixed server code; the UI shows its own sentence for it (lib/verification.ts). */
  reason?: string | null;
}

export interface VerificationRecordOut {
  id: string;
  version_id: string;
  requested_by: string;
  recomputed_hash: string | null;
  stored_hash: string;
  onchain_hash: string | null;
  result: VerificationResult;
  created_at: string;
  reason?: string | null;
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
