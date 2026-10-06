/**
 * The five classification / clearance levels, lowest first (SEC-02, D-051). Mirrors
 * app.core.clearance.LEVELS on the server, which is the only place access is decided: this list
 * only fills selects and labels. Nothing here hides or allows anything.
 */
export const LEVELS = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED", "TOP_SECRET"] as const;

export type Level = (typeof LEVELS)[number];

const LABELS: Record<Level, string> = {
  PUBLIC: "Public",
  INTERNAL: "Internal",
  CONFIDENTIAL: "Confidential",
  RESTRICTED: "Restricted",
  TOP_SECRET: "Top secret",
};

/** A readable name for a level; anything that is not a known level is shown as it is. */
export function levelLabel(value: string): string {
  return LABELS[value as Level] ?? value;
}
