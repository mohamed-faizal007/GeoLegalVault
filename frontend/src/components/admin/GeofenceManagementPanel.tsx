import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { createGeofence, listGeofences, updateGeofence } from "../../api/geofences";
import ErrorBanner from "../ErrorBanner";
import Spinner from "../Spinner";

const EXAMPLE_RING = `[
  [78.14, 11.66],
  [78.16, 11.66],
  [78.16, 11.68],
  [78.14, 11.68]
]`;

function parseRing(raw: string): number[][] {
  let positions: unknown;
  try {
    positions = JSON.parse(raw);
  } catch {
    throw new Error("Ring must be valid JSON: an array of [lng, lat] pairs.");
  }
  if (!Array.isArray(positions) || positions.length < 3) {
    throw new Error("Ring needs at least 3 [lng, lat] positions.");
  }
  if (positions.length > 100) {
    throw new Error("Ring exceeds the 100-vertex cap.");
  }
  const ring = positions.map((p) => {
    if (!Array.isArray(p) || p.length !== 2 || typeof p[0] !== "number" || typeof p[1] !== "number") {
      throw new Error("Each position must be [longitude, latitude] numbers.");
    }
    const [lng, lat] = p;
    if (lng < -180 || lng > 180) throw new Error(`Longitude out of range: ${lng}`);
    if (lat < -90 || lat > 90) throw new Error(`Latitude out of range: ${lat}`);
    return [lng, lat];
  });
  // Auto-close: the server requires the ring's first and last position to match.
  const first = ring[0];
  const last = ring[ring.length - 1];
  if (first[0] !== last[0] || first[1] !== last[1]) {
    ring.push(first);
  }
  return ring;
}

export default function GeofenceManagementPanel() {
  const queryClient = useQueryClient();
  const geofencesQuery = useQuery({
    queryKey: ["admin", "geofences"],
    queryFn: () => listGeofences(1, 100),
  });

  const [name, setName] = useState("");
  const [ringText, setRingText] = useState(EXAMPLE_RING);

  const createMutation = useMutation({
    mutationFn: () => {
      const ring = parseRing(ringText);
      return createGeofence({ name, region: { type: "Polygon", coordinates: [ring] } });
    },
    onSuccess: () => {
      setName("");
      setRingText(EXAMPLE_RING);
      queryClient.invalidateQueries({ queryKey: ["admin", "geofences"] });
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      updateGeofence(id, { active: !active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "geofences"] }),
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    createMutation.mutate();
  }

  return (
    <div className="space-y-6">
      <form
        onSubmit={handleSubmit}
        className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
      >
        <h2 className="text-sm font-semibold text-slate-800">Create geofence</h2>
        <input
          required
          placeholder="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <div>
          <p className="mb-1 text-xs font-medium text-slate-500">
            Polygon ring — an array of [longitude, latitude] pairs (GeoJSON order; closes
            automatically if you omit the repeated first point)
          </p>
          <textarea
            value={ringText}
            onChange={(e) => setRingText(e.target.value)}
            rows={6}
            className="w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-xs"
          />
        </div>
        {createMutation.error && <ErrorBanner error={createMutation.error} />}
        <button
          type="submit"
          disabled={createMutation.isPending}
          className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {createMutation.isPending ? "Creating…" : "Create geofence"}
        </button>
      </form>

      <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
        {geofencesQuery.isLoading && <Spinner label="Loading geofences…" />}
        {geofencesQuery.error && (
          <div className="p-4">
            <ErrorBanner error={geofencesQuery.error} />
          </div>
        )}
        {geofencesQuery.data && (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Vertices</th>
                <th className="px-4 py-2 font-medium">Active</th>
                <th className="px-4 py-2 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {geofencesQuery.data.items.map((fence) => (
                <tr key={fence.id}>
                  <td className="px-4 py-2">{fence.name}</td>
                  <td className="px-4 py-2 text-slate-500">
                    {fence.region.coordinates[0]?.length ?? 0}
                  </td>
                  <td className="px-4 py-2">
                    {fence.active ? (
                      <span className="text-emerald-600">Active</span>
                    ) : (
                      <span className="text-slate-400">Deactivated</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => toggleActiveMutation.mutate({ id: fence.id, active: fence.active })}
                      className="text-xs font-medium text-slate-600 underline"
                    >
                      {fence.active ? "Deactivate" : "Reactivate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
