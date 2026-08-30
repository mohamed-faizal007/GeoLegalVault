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
      <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
        Requesting your current location…
      </div>
    );
  }

  if (error || !coords) {
    return (
      <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        <p className="font-medium">Location required</p>
        <p className="mt-1">
          {error?.message ?? "Your location could not be determined."} This action requires a
          location reading — the server will decide whether it's from an authorized area.
        </p>
        <button
          type="button"
          onClick={refresh}
          className="mt-2 rounded border border-amber-300 bg-white px-3 py-1 text-xs font-medium text-amber-800 hover:bg-amber-100"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <>
      <p className="mb-3 text-xs text-slate-400">
        Location reading: {coords.lat.toFixed(5)}, {coords.lng.toFixed(5)} (±
        {Math.round(coords.accuracy)}m){" "}
        <button type="button" onClick={refresh} className="ml-1 text-slate-500 underline">
          refresh
        </button>
      </p>
      {children(coords, refresh)}
    </>
  );
}
