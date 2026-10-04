import { describe, expect, it } from "vitest";

import { canRequestRetry, describeAnchorError, stateGuidance } from "../anchorAttention";
import { hasPermission, PERMISSIONS, ROLES } from "../permissions";

describe("describeAnchorError", () => {
  it("maps every fixed backend code to a sentence and keeps the code", () => {
    const codes = [
      "RPC_UNREACHABLE",
      "INSUFFICIENT_FUNDS",
      "ALREADY_ANCHORED",
      "NOT_AUTHORIZED",
      "REVERTED",
      "NOT_CONFIGURED",
      "ANCHOR_FAILED",
      "TX_DROPPED",
      "RETRIES_EXHAUSTED",
      "STORED_OBJECT_MISSING",
    ];
    for (const code of codes) {
      const described = describeAnchorError(code);
      expect(described.code).toBe(code);
      expect(described.label).not.toContain(code); // a sentence, not the code
      expect(described.label.endsWith(".")).toBe(true);
    }
  });

  it("never echoes a value it does not recognise", () => {
    const described = describeAnchorError("HTTPSConnectionPool(...): url: /v2/SECRET");
    expect(described.code).toBeNull();
    expect(described.label).toBe("Anchoring has not completed.");
    expect(JSON.stringify(described)).not.toContain("SECRET");
  });

  it("handles no error", () => {
    expect(describeAnchorError(null)).toEqual({
      label: "No error has been recorded yet.",
      code: null,
    });
  });
});

describe("stateGuidance / canRequestRetry", () => {
  it("tells non-admins that an administrator must act", () => {
    expect(stateGuidance("PERMANENT_FAILURE", false)).toMatch(/administrator needs to request/i);
    expect(stateGuidance("NEEDS_ADMIN_RETRY", false)).toMatch(/administrator needs to request/i);
    expect(stateGuidance("PERMANENT_FAILURE", true)).not.toMatch(/administrator needs/i);
  });

  it("does not offer a retry while a transaction is in flight, or when the server refuses", () => {
    expect(canRequestRetry("AWAITING_CONFIRMATION", true)).toBe(false);
    expect(canRequestRetry("PERMANENT_FAILURE", false)).toBe(false);
    expect(canRequestRetry("PERMANENT_FAILURE", true)).toBe(true);
    expect(canRequestRetry("RETRYING", true)).toBe(true);
  });
});

describe("anchor permissions mirror the backend map (UX only; the server decides)", () => {
  it("anchor:view for Administrator, Legal Officer, Auditor; anchor:retry for Administrator only", () => {
    const viewers = new Set<string>([ROLES.ADMINISTRATOR, ROLES.LEGAL_OFFICER, ROLES.AUDITOR]);
    for (const role of Object.values(ROLES)) {
      expect(hasPermission(role, PERMISSIONS.ANCHOR_VIEW)).toBe(viewers.has(role));
      expect(hasPermission(role, PERMISSIONS.ANCHOR_RETRY)).toBe(role === ROLES.ADMINISTRATOR);
    }
  });
});
