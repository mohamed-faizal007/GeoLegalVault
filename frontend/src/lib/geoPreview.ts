/** Human-readable description of a GeoJSON ring (Guardrail #9, D-027). This is an
 * advisory aid for the admin: it makes a swapped [lat, lng] ring visible as "the Arctic",
 * but it cannot detect a swap by itself and the server does not rely on it. */

export interface RingSummary {
  centre: string;
  extent: string;
}

function formatPoint(lng: number, lat: number): string {
  const ns = lat >= 0 ? "N" : "S";
  const ew = lng >= 0 ? "E" : "W";
  return `${Math.abs(lat).toFixed(4)}°${ns} ${Math.abs(lng).toFixed(4)}°${ew}`;
}

/** `ring` is [lng, lat] pairs. Returns null for an empty ring. */
export function describeRing(ring: number[][]): RingSummary | null {
  // Drop the closing duplicate so the centre is not biased toward the first vertex.
  const first = ring[0];
  const last = ring[ring.length - 1];
  const open = first && last && first[0] === last[0] && first[1] === last[1] ? ring.slice(0, -1) : ring;
  if (open.length === 0) return null;

  const lngs = open.map((p) => p[0]);
  const lats = open.map((p) => p[1]);
  const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;
  return {
    centre: formatPoint(mean(lngs), mean(lats)),
    extent: `${formatPoint(Math.min(...lngs), Math.min(...lats))} to ${formatPoint(Math.max(...lngs), Math.max(...lats))}`,
  };
}
