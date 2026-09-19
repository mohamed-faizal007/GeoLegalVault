import type { ReactNode } from "react";

import type { GeoCoords } from "../api/http";
import { useGeoLocation } from "../hooks/useGeoLocation";

/**
 * Wraps a sensitive form (Upload, Amendment Request) so it can't be
 * submitted until a fresh browser location reading is in hand. This is
 * strictly a UX convenience — it never decides allow/deny itself. The
 * coordinates are only ever a claim; the server runs the real geofence
 * check (Guardrail #5/#6) and can still reject the request outside the
 * authorized area or on a stale/low-accuracy reading.
 */
export default function LocationGate({
  children,
}: {
  children: (coords: GeoCoords, refresh: () => void) => ReactNode;
}) {
  const { coords, error, loading, refresh } = useGeoLocation(true);

  if (loading) {
    return (
      <div className="flex items-center gap-2.5 rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm text-muted">
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/15 border-t-brand-400" />
        Requesting your current location…
      </div>
    );
  }

  if (error || !coords) {
    return (
      <div role="alert" className="rounded-lg border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
        <p className="font-medium">Location required</p>
        <p className="mt-1">
          {error?.message ?? "Your location could not be determined."} This action requires a
          location reading — the server will decide whether it's from an authorized area.
        </p>
        <button
          type="button"
          onClick={refresh}
          className="mt-2 rounded-md border border-amber-400/40 bg-amber-500/10 px-3 py-1 text-xs font-medium text-amber-100 transition-colors duration-150 hover:bg-amber-500/20"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <>
      <p className="mb-3 flex items-center gap-1.5 text-xs text-muted">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="h-3.5 w-3.5 text-emerald-400" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 21s7-6.1 7-11.5A7 7 0 0 0 5 9.5C5 14.9 12 21 12 21Zm0-9a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" />
        </svg>
        Location reading: {coords.lat.toFixed(5)}, {coords.lng.toFixed(5)} (±
        {Math.round(coords.accuracy)}m){" "}
        <button type="button" onClick={refresh} className="ml-1 text-muted underline decoration-white/25 underline-offset-2 transition-colors duration-150 hover:text-brand-300">
          refresh
        </button>
      </p>
      {children(coords, refresh)}
    </>
  );
}
