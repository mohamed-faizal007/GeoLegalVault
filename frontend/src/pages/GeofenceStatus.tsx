import { useEffect, useState } from "react";

import { useGeoLocation } from "../hooks/useGeoLocation";

const ACCURACY_HINT_MAX_M = 100; // mirrors the server's GEO_ACCURACY_MAX_M default — a hint only

/** Reading the wall clock directly during render is impure (React may
 * re-render for unrelated reasons and produce a different "now" each time)
 * — so "now" lives in state, ticking once a second via an effect instead. */
function useNowSeconds(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  return now / 1000;
}

export default function GeofenceStatus() {
  const { coords, error, loading, refresh } = useGeoLocation(true);
  const nowSeconds = useNowSeconds();

  return (
    <div className="max-w-xl space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight text-ink">Geofence Status</h1>
      <p className="text-sm text-muted">
        This shows what your browser currently reports. Whether a specific action (upload,
        download, approve, amend) is actually permitted from this location is always decided by
        the server at the moment you take that action — this page cannot and does not make that
        call.
      </p>

      <div className="card p-6">
        {loading && (
          <div className="flex items-center gap-2.5 text-sm text-muted">
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/15 border-t-brand-600" />
            Requesting your location…
          </div>
        )}

        {error && (
          <div className="rounded-md border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
            {error.message}
          </div>
        )}

        {coords && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-xs uppercase tracking-wide text-faint">Latitude</p>
                <p className="mt-0.5 font-mono text-ink">{coords.lat.toFixed(6)}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-faint">Longitude</p>
                <p className="mt-0.5 font-mono text-ink">{coords.lng.toFixed(6)}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-faint">Accuracy</p>
                <p className="mt-0.5 text-ink">{Math.round(coords.accuracy)} m</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-faint">Reading age</p>
                <p className="mt-0.5 text-ink">
                  {Math.max(0, Math.round(nowSeconds - coords.timestamp))}s ago
                </p>
              </div>
            </div>

            <span
              className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${
                coords.accuracy <= ACCURACY_HINT_MAX_M
                  ? "bg-emerald-500/10 text-emerald-300 ring-emerald-400/30"
                  : "bg-amber-500/10 text-amber-300 ring-amber-400/30"
              }`}
            >
              {coords.accuracy <= ACCURACY_HINT_MAX_M
                ? "Accuracy looks sufficient"
                : `Accuracy is coarser than the typical ${ACCURACY_HINT_MAX_M}m threshold — a real action may be rejected`}
            </span>
          </div>
        )}

        <button type="button" onClick={refresh} className="btn-secondary mt-4">
          Refresh location
        </button>
      </div>

      <p className="text-xs text-faint">
        Note: browser geolocation can be overridden by the device or browser, so this reading is a
        policy input, not a security guarantee. The server independently verifies every sensitive
        request.
      </p>
    </div>
  );
}
