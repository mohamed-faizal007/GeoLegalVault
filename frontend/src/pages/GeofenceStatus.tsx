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
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Geofence Status</h1>
      <p className="text-sm text-slate-500">
        This shows what your browser currently reports. Whether a specific action (upload,
        download, approve, amend) is actually permitted from this location is always decided by
        the server at the moment you take that action — this page cannot and does not make that
        call.
      </p>

      <div className="card p-6">
        {loading && (
          <div className="flex items-center gap-2.5 text-sm text-slate-500">
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600" />
            Requesting your location…
          </div>
        )}

        {error && (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {error.message}
          </div>
        )}

        {coords && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-400">Latitude</p>
                <p className="mt-0.5 font-mono text-slate-800">{coords.lat.toFixed(6)}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-400">Longitude</p>
                <p className="mt-0.5 font-mono text-slate-800">{coords.lng.toFixed(6)}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-400">Accuracy</p>
                <p className="mt-0.5 text-slate-800">{Math.round(coords.accuracy)} m</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-400">Reading age</p>
                <p className="mt-0.5 text-slate-800">
                  {Math.max(0, Math.round(nowSeconds - coords.timestamp))}s ago
                </p>
              </div>
            </div>

            <span
              className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${
                coords.accuracy <= ACCURACY_HINT_MAX_M
                  ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20"
                  : "bg-amber-50 text-amber-700 ring-amber-600/20"
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

      <p className="text-xs text-slate-400">
        Note: browser geolocation can be overridden by the device or browser, so this reading is a
        policy input, not a security guarantee. The server independently verifies every sensitive
        request.
      </p>
    </div>
  );
}
