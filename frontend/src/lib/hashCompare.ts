/**
 * Display-only comparison of the hash recorded in the database with the hash read live from the
 * chain. The verification logic itself is the server's (POST /verify); this only decides which
 * words and colour the anchor page shows next to the two values.
 */
import type { AnchorOut } from "../api/blockchain";

export type HashComparison = "MATCH" | "MISMATCH" | "NOT_ON_CHAIN" | "UNAVAILABLE";

function normalize(hash: string): string {
  return hash.trim().toLowerCase().replace(/^0x/, "");
}

export function compareHashes(anchor: Pick<AnchorOut, "sha256" | "onchain">): HashComparison {
  if (!anchor.onchain) return "UNAVAILABLE";
  if (!anchor.onchain.exists) return "NOT_ON_CHAIN";
  return normalize(anchor.onchain.hash) === normalize(anchor.sha256) ? "MATCH" : "MISMATCH";
}

export const COMPARISON_TEXT: Record<HashComparison, { label: string; detail: string }> = {
  MATCH: {
    label: "Match",
    detail: "The recorded hash is identical to the hash read from the chain just now.",
  },
  MISMATCH: {
    label: "Mismatch",
    detail:
      "The recorded hash differs from the hash on the chain. Run a verification on the document page to see which side changed.",
  },
  NOT_ON_CHAIN: {
    label: "Not found on chain",
    detail: "The chain holds no anchor for this version yet, so there is nothing to compare with.",
  },
  UNAVAILABLE: {
    label: "Not compared",
    detail:
      "The chain could not be read, or the anchor has no transaction yet. The recorded hash is shown without a live comparison.",
  },
};
