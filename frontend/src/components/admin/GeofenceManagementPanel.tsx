import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState, type FormEvent } from "react";

import { createGeofence, listGeofences, updateGeofence, type GeofenceOut } from "../../api/geofences";
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

/** Inverse of parseRing's shape, for pre-filling the edit form from a
 * fence's current region. */
function formatRing(ring: number[][]): string {
  return `[\n${ring.map((p) => `  [${p[0]}, ${p[1]}]`).join(",\n")}\n]`;
}

/** Inline editor for name / region (PATCH /geofences/{id}), mirroring
 * UserEditForm's inline-in-table pattern for users. */
function GeofenceEditForm({
  fence,
  onDone,
}: {
  fence: GeofenceOut;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(fence.name);
  const [ringText, setRingText] = useState(formatRing(fence.region.coordinates[0] ?? []));

  const mutation = useMutation({
    mutationFn: () => {
      const ring = parseRing(ringText);
      return updateGeofence(fence.id, { name, region: { type: "Polygon", coordinates: [ring] } });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "geofences"] });
      onDone();
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    mutation.mutate();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 bg-raised/40 p-4">
      <input
        required
        aria-label="Geofence name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="input"
      />
      <div>
        <p className="mb-1 text-xs font-medium text-muted">
          Polygon ring — an array of [longitude, latitude] pairs (GeoJSON order; closes
          automatically if you omit the repeated first point)
        </p>
        <textarea
          aria-label="Polygon ring"
          value={ringText}
          onChange={(e) => setRingText(e.target.value)}
          rows={6}
          className="input font-mono text-xs"
        />
      </div>
      {mutation.error && <ErrorBanner error={mutation.error} />}
      <div className="flex gap-2">
        <button type="submit" disabled={mutation.isPending} className="btn-primary btn-sm">
          {mutation.isPending ? "Saving…" : "Save changes"}
        </button>
        <button type="button" onClick={onDone} className="btn-secondary btn-sm">
          Cancel
        </button>
      </div>
    </form>
  );
}

export default function GeofenceManagementPanel() {
  const queryClient = useQueryClient();
  const geofencesQuery = useQuery({
    queryKey: ["admin", "geofences"],
    queryFn: () => listGeofences(1, 100),
  });
  const [editingId, setEditingId] = useState<string | null>(null);

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
      <form onSubmit={handleSubmit} className="card space-y-3 p-4">
        <h2 className="text-sm font-semibold text-ink">Create geofence</h2>
        <input
          required
          placeholder="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="input"
        />
        <div>
          <p className="mb-1 text-xs font-medium text-muted">
            Polygon ring — an array of [longitude, latitude] pairs (GeoJSON order; closes
            automatically if you omit the repeated first point)
          </p>
          <textarea
            value={ringText}
            onChange={(e) => setRingText(e.target.value)}
            rows={6}
            className="input font-mono text-xs"
          />
        </div>
        {createMutation.error && <ErrorBanner error={createMutation.error} />}
        <button type="submit" disabled={createMutation.isPending} className="btn-primary">
          {createMutation.isPending ? "Creating…" : "Create geofence"}
        </button>
      </form>

      <div className="card overflow-hidden">
        {geofencesQuery.isLoading && <Spinner label="Loading geofences…" />}
        {geofencesQuery.error && (
          <div className="p-4">
            <ErrorBanner error={geofencesQuery.error} />
          </div>
        )}
        {geofencesQuery.data && (
          <table className="w-full text-left text-sm">
            <thead className="table-head">
              <tr>
                <th className="px-4 py-2.5 font-medium">Name</th>
                <th className="px-4 py-2.5 font-medium">Vertices</th>
                <th className="px-4 py-2.5 font-medium">Active</th>
                <th className="px-4 py-2.5 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {geofencesQuery.data.items.map((fence) => (
                <Fragment key={fence.id}>
                  <tr className="table-row-hover">
                    <td className="px-4 py-2.5">{fence.name}</td>
                    <td className="px-4 py-2.5 text-muted">
                      {fence.region.coordinates[0]?.length ?? 0}
                    </td>
                    <td className="px-4 py-2.5">
                      {fence.active ? (
                        <span className="text-emerald-300">Active</span>
                      ) : (
                        <span className="text-faint">Deactivated</span>
                      )}
                    </td>
                    <td className="space-x-3 px-4 py-2.5 text-right">
                      <button
                        type="button"
                        onClick={() => setEditingId(editingId === fence.id ? null : fence.id)}
                        className="text-xs font-medium text-brand-400 underline hover:text-brand-300"
                      >
                        {editingId === fence.id ? "Close" : "Edit"}
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          toggleActiveMutation.mutate({ id: fence.id, active: fence.active })
                        }
                        className="text-xs font-medium text-brand-400 underline hover:text-brand-300"
                      >
                        {fence.active ? "Deactivate" : "Reactivate"}
                      </button>
                    </td>
                  </tr>
                  {editingId === fence.id && (
                    <tr>
                      <td colSpan={4} className="p-0">
                        <GeofenceEditForm fence={fence} onDone={() => setEditingId(null)} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
