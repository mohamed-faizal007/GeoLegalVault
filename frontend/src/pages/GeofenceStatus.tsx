import { useGeoLocation } from "../hooks/useGeoLocation";

const ACCURACY_HINT_MAX_M = 100; // mirrors the server's GEO_ACCURACY_MAX_M default — a hint only

export default function GeofenceStatus() {
  const { coords, error, loading, refresh } = useGeoLocation(true);

  return (
    <div className="max-w-xl space-y-4">
      <h1 className="text-lg font-semibold text-slate-900">Geofence Status</h1>
      <p className="text-sm text-slate-500">
        This shows what your browser currently reports. Whether a specific action (upload,
        download, approve, amend) is actually permitted from this location is always decided by
        the server at the moment you take that action — this page cannot and does not make that
        call.
      </p>

      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        {loading && <p className="text-sm text-slate-500">Requesting your location…</p>}

        {error && (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {error.message}
          </div>
        )}

        {coords && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-xs uppercase text-slate-400">Latitude</p>
                <p className="font-mono text-slate-800">{coords.lat.toFixed(6)}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-slate-400">Longitude</p>
                <p className="font-mono text-slate-800">{coords.lng.toFixed(6)}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-slate-400">Accuracy</p>
                <p className="text-slate-800">{Math.round(coords.accuracy)} m</p>
              </div>
              <div>
                <p className="text-xs uppercase text-slate-400">Reading age</p>
                <p className="text-slate-800">
                  {Math.max(0, Math.round(Date.now() / 1000 - coords.timestamp))}s ago
                </p>
              </div>
            </div>

            <span
              className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${
                coords.accuracy <= ACCURACY_HINT_MAX_M
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-amber-100 text-amber-700"
              }`}
            >
              {coords.accuracy <= ACCURACY_HINT_MAX_M
                ? "Accuracy looks sufficient"
                : `Accuracy is coarser than the typical ${ACCURACY_HINT_MAX_M}m threshold — a real action may be rejected`}
            </span>
          </div>
        )}

        <button
          type="button"
          onClick={refresh}
          className="mt-4 rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
        >
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
