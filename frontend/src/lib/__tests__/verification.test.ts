import { describe, expect, it } from "vitest";

import { statusTone } from "../status";
import {
  GENERIC_REASON,
  isClearableFlag,
  reasonText,
  RESULT_COPY,
  resultCopy,
} from "../verification";

describe("verification copy (D-050)", () => {
  it("every result has a headline, a sentence and its own icon", () => {
    const entries = Object.values(RESULT_COPY);
    expect(entries).toHaveLength(6);
    for (const copy of entries) {
      expect(copy.headline.length).toBeGreaterThan(3);
      expect(copy.explanation.length).toBeGreaterThan(20);
    }
    expect(new Set(entries.map((c) => c.iconPath)).size).toBe(entries.length);
    expect(new Set(entries.map((c) => c.headline)).size).toBe(entries.length);
  });

  it("maps known reason codes to fixed sentences and never echoes anything else", () => {
    expect(reasonText(null)).toBeNull();
    expect(reasonText("CHAIN_TIMEOUT")).toBe("The blockchain node did not answer in time.");
    const leaky = "Max retries exceeded with url: /v2/SECRETKEYABCDEF123456";
    expect(reasonText(leaky)).toBe(GENERIC_REASON);
    expect(reasonText(leaky)).not.toContain("SECRETKEY");
  });

  it("an unknown result is shown as 'could not check', never as VERIFIED", () => {
    expect(resultCopy("NEW_THING").headline).toBe(RESULT_COPY.CHAIN_UNREACHABLE.headline);
  });

  it("the new states are not styled as success or as plain neutral", () => {
    expect(statusTone("ANCHOR_MISSING")).toBe("danger");
    expect(statusTone("FILE_MISSING")).toBe("danger");
    expect(statusTone("CHAIN_UNREACHABLE")).toBe("warn");
    expect(statusTone("UNCONFIRMED")).toBe("warn");
  });

  it("only TAMPERED and UNCONFIRMED are clearable flags", () => {
    expect(isClearableFlag("TAMPERED")).toBe(true);
    expect(isClearableFlag("UNCONFIRMED")).toBe(true);
    expect(isClearableFlag(null)).toBe(false);
    expect(isClearableFlag("OTHER")).toBe(false);
  });
});
