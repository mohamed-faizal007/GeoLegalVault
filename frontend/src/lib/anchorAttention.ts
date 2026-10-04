/**
 * Plain-language text for the anchor-attention banner (REL-01, D-041).
 *
 * The backend only ever sends a fixed error *code* (never raw exception text, which
 * could embed an RPC URL; D-020). This still refuses to render anything it does not
 * recognise: an unknown value becomes a generic sentence, so a future backend change
 * can never put raw error text or RPC details on screen.
 */
import type { AnchorAttentionState } from "../api/blockchain";

const ERROR_LABELS: Record<string, string> = {
  RPC_UNREACHABLE: "The blockchain network could not be reached.",
  INSUFFICIENT_FUNDS: "The service wallet is out of funds.",
  ALREADY_ANCHORED: "The chain already holds an anchor for this version.",
  NOT_AUTHORIZED: "The service wallet is not authorised to anchor.",
  REVERTED: "The chain rejected the anchoring transaction.",
  NOT_CONFIGURED: "Blockchain anchoring is not configured.",
  ANCHOR_FAILED: "Anchoring failed for an unspecified reason.",
  TX_DROPPED: "The transaction was lost before it was confirmed.",
  RETRIES_EXHAUSTED: "Automatic retries were used up.",
  STORED_OBJECT_MISSING: "The stored file for this version is missing.",
};

export function describeAnchorError(code: string | null): { label: string; code: string | null } {
  if (!code) return { label: "No error has been recorded yet.", code: null };
  const label = ERROR_LABELS[code];
  if (label === undefined) return { label: "Anchoring has not completed.", code: null };
  return { label, code };
}

/** What is happening, and who has to act, in one sentence. */
export function stateGuidance(state: AnchorAttentionState, canRetry: boolean): string {
  switch (state) {
    case "RETRYING":
      return "The system is retrying automatically.";
    case "AWAITING_CONFIRMATION":
      return "The transaction was sent and is waiting for the network to confirm it.";
    case "PERMANENT_FAILURE":
      return canRetry
        ? "Automatic retries have stopped. Fix the cause, then request a retry."
        : "Automatic retries have stopped. An administrator needs to request a retry.";
    case "NEEDS_ADMIN_RETRY":
      return canRetry
        ? "Stuck for too long to retry automatically. Request a retry to try again."
        : "Stuck for too long to retry automatically. An administrator needs to request a retry.";
  }
}

/** A retry cannot be requested while a transaction is in flight (the server refuses it too). */
export function canRequestRetry(state: AnchorAttentionState, serverAllows: boolean): boolean {
  return serverAllows && state !== "AWAITING_CONFIRMATION";
}
