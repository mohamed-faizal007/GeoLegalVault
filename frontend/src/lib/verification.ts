/**
 * Wording for verification results and integrity flags (D-050, REL-04). Defined once so the
 * Verification page, the document page and the lists say the same thing.
 *
 * Nothing here is ever taken from a server response: the API returns result and reason as
 * fixed codes, and the UI maps them to the sentences below. An unknown reason code renders a
 * generic sentence, never the code or any text the server sent (Guardrail #2: an error string
 * can embed an RPC URL with its key).
 */
import type { VerificationResult } from "../api/verify";

export type ResultTone = "ok" | "danger" | "warn" | "neutral";

export interface ResultCopy {
  headline: string;
  explanation: string;
  tone: ResultTone;
  /** SVG path: every result has its own shape, so it is not told apart by colour alone. */
  iconPath: string;
}

export const RESULT_COPY: Record<VerificationResult, ResultCopy> = {
  VERIFIED: {
    headline: "VERIFIED",
    explanation:
      "The stored file, the hash recorded at upload and the hash anchored on the blockchain all agree.",
    tone: "ok",
    iconPath: "m5 13 4 4L19 7",
  },
  MISMATCH: {
    headline: "MISMATCH — tamper detected",
    explanation:
      "The current file does not match the recorded or anchored hash. The document was flagged.",
    tone: "danger",
    iconPath: "M6 6l12 12M18 6 6 18",
  },
  NOT_ANCHORED: {
    headline: "NOT ANCHORED YET",
    explanation:
      "Our records do not show this version as anchored on the blockchain, so there is nothing to compare against yet.",
    tone: "neutral",
    iconPath: "M6 12h12",
  },
  ANCHOR_MISSING: {
    headline: "ANCHOR MISSING",
    explanation:
      "Our records say this version was anchored, but the blockchain has no matching entry. This can happen if the test network was reset. Integrity could not be confirmed, and the document was flagged for an administrator.",
    tone: "danger",
    iconPath: "M12 7v6M12 17h.01",
  },
  FILE_MISSING: {
    headline: "STORED FILE MISSING",
    explanation:
      "The stored file for this version was not found, so it could not be checked. Integrity could not be confirmed, and the document was flagged for an administrator.",
    tone: "danger",
    iconPath: "M8 4h6l4 4v12H8zM5 5l14 14",
  },
  CHAIN_UNREACHABLE: {
    headline: "COULD NOT CHECK THE BLOCKCHAIN",
    explanation:
      "No result: the blockchain could not be read, so this version was neither confirmed nor flagged. Try again later.",
    tone: "warn",
    iconPath: "M9.5 9a2.5 2.5 0 1 1 3.8 2.1c-.8.5-1.3 1-1.3 2M12 17h.01",
  },
};

/** The result of an unrecognised (newer) server code: shown as a plain "could not check". */
export function resultCopy(result: string): ResultCopy {
  return RESULT_COPY[result as VerificationResult] ?? RESULT_COPY.CHAIN_UNREACHABLE;
}

const REASON_COPY: Record<string, string> = {
  RPC_UNREACHABLE: "The blockchain node could not be reached.",
  CHAIN_TIMEOUT: "The blockchain node did not answer in time.",
  NOT_CONFIGURED: "Blockchain access is not configured on the server.",
  CONTRACT_NOT_DEPLOYED:
    "No anchoring contract was found at the configured address (the network may have been reset or redeployed).",
  CHAIN_READ_FAILED: "The blockchain returned an answer that could not be used.",
};

export const GENERIC_REASON = "The blockchain could not be read.";

/** Fixed sentence for a reason code; null when there is no reason. Never echoes the input. */
export function reasonText(reason: string | null | undefined): string | null {
  if (!reason) return null;
  return REASON_COPY[reason] ?? GENERIC_REASON;
}

/** Integrity flags an Administrator may clear (D-025, D-049). */
export const CLEARABLE_FLAGS = ["TAMPERED", "UNCONFIRMED"] as const;

export function isClearableFlag(flag: string | null | undefined): boolean {
  return flag != null && (CLEARABLE_FLAGS as readonly string[]).includes(flag);
}

export const UNCONFIRMED_BANNER =
  "A verification run could not confirm this document's integrity: the blockchain record or the stored file is missing. This is not proof of tampering, and it does not block any action on the document. An administrator can clear the flag once a re-verification passes.";
