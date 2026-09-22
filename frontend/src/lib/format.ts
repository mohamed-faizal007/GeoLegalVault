export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString();
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`;
}

export function truncateHash(hash: string, chars = 10): string {
  if (hash.length <= chars * 2 + 3) return hash;
  return `${hash.slice(0, chars)}…${hash.slice(-chars)}`;
}

/** Parses a YYYY-MM-DD value from <input type="date"> as a *local* calendar day. */
function parseLocalDay(day: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
  if (!match) return null;
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

/** Start of the given local day as a UTC ISO timestamp (for `date_from`). */
export function localDayStartISO(day: string): string | undefined {
  return parseLocalDay(day)?.toISOString();
}

/** Last millisecond of the given local day as a UTC ISO timestamp (for `date_to`),
 * so an inclusive "to" date doesn't drop everything that happened on that day. */
export function localDayEndISO(day: string): string | undefined {
  const start = parseLocalDay(day);
  if (!start) return undefined;
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return new Date(end.getTime() - 1).toISOString();
}
