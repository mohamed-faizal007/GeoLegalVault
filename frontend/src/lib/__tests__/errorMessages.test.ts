import { describe, expect, it } from "vitest";

import { ApiError } from "../../api/http";
import { describeError } from "../errorMessages";

describe("describeError, classification and access (D-052)", () => {
  it.each([
    ["INVALID_CLASSIFICATION", /choose one of the listed/i],
    ["CLASSIFICATION_NOT_ALLOWED", /above your own clearance/i],
    ["CLASSIFICATION_IMMUTABLE", /can't be changed after upload/i],
    ["SELF_CLEARANCE_CHANGE", /another administrator/i],
  ])("%s gets fixed plain text, not the server's wording", (code, expected) => {
    const { message } = describeError(new ApiError(400, code, "RAW SERVER TEXT"));
    expect(message).toMatch(expected);
    expect(message).not.toContain("RAW SERVER TEXT");
  });

  it("gives a hidden and a missing document the same words", () => {
    const hidden = describeError(new ApiError(404, "HTTP_404", "Document not found"));
    const missing = describeError(new ApiError(404, "HTTP_404", "Document not found"));
    expect(hidden).toEqual(missing);
    expect(hidden.message).toMatch(/couldn't be found, or you don't have access/i);
  });
});
