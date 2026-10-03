import { describe, expect, it } from "vitest";

import { describeRing } from "../geoPreview";

describe("describeRing", () => {
  it("reports the approximate centre as lat/lng with hemispheres, ignoring the closing vertex", () => {
    const ring = [
      [78.14, 11.66],
      [78.16, 11.66],
      [78.16, 11.68],
      [78.14, 11.68],
      [78.14, 11.66],
    ];
    expect(describeRing(ring)?.centre).toBe("11.6700°N 78.1500°E");
  });

  it("uses S and W for negative coordinates", () => {
    expect(describeRing([
        [-58.5, -34.5],
        [-58.3, -34.5],
        [-58.4, -34.8],
      ])?.centre).toBe("34.6000°S 58.4000°W");
  });

  it("returns null for an empty ring", () => {
    expect(describeRing([])).toBeNull();
  });
});
