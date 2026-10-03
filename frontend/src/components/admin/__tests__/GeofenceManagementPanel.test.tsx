import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import GeofenceManagementPanel from "../GeofenceManagementPanel";

const listGeofencesMock = vi.fn();
const updateGeofenceMock = vi.fn();
const createGeofenceMock = vi.fn();

vi.mock("../../../api/geofences", async () => {
  const actual =
    await vi.importActual<typeof import("../../../api/geofences")>("../../../api/geofences");
  return {
    ...actual,
    listGeofences: (...a: unknown[]) => listGeofencesMock(...a),
    updateGeofence: (...a: unknown[]) => updateGeofenceMock(...a),
    createGeofence: (...a: unknown[]) => createGeofenceMock(...a),
  };
});

const fence = {
  id: "g-1",
  name: "HQ Campus",
  region: {
    type: "Polygon" as const,
    coordinates: [
      [
        [78.14, 11.66],
        [78.16, 11.66],
        [78.16, 11.68],
        [78.14, 11.68],
        [78.14, 11.66],
      ],
    ],
  },
  center: null,
  radius_m: null,
  active: true,
  created_at: "2026-01-01T00:00:00Z",
};

function renderPanel() {
  listGeofencesMock.mockResolvedValue({ items: [fence], page: 1, limit: 100, total: 1 });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <GeofenceManagementPanel />
    </QueryClientProvider>,
  );
}

describe("GeofenceManagementPanel editing", () => {
  afterEach(() => vi.clearAllMocks());

  it("pre-fills the edit form with the fence's current name and ring, and saves via PATCH", async () => {
    updateGeofenceMock.mockResolvedValue(fence);
    renderPanel();

    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    const name = screen.getByLabelText("Geofence name") as HTMLInputElement;
    expect(name.value).toBe("HQ Campus");
    const ring = screen.getByLabelText("Polygon ring") as HTMLTextAreaElement;
    expect(ring.value).toContain("78.14");

    await userEvent.clear(name);
    await userEvent.type(name, "HQ Campus (renamed)");
    await userEvent.click(screen.getByRole("button", { name: /save changes/i }));

    expect(updateGeofenceMock).toHaveBeenCalledWith("g-1", {
      name: "HQ Campus (renamed)",
      region: { type: "Polygon", coordinates: [fence.region.coordinates[0]] },
    });
  });

  it("closes the edit form on Cancel without saving", async () => {
    renderPanel();

    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    expect(screen.getByLabelText("Geofence name")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(screen.queryByLabelText("Geofence name")).not.toBeInTheDocument();
    expect(updateGeofenceMock).not.toHaveBeenCalled();
  });
});

describe("GeofenceManagementPanel location preview (D-027)", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows where the ring lands and blocks create until the admin ticks the confirmation", async () => {
    createGeofenceMock.mockResolvedValue(fence);
    renderPanel();

    await userEvent.type(await screen.findByPlaceholderText("Name"), "HQ");
    expect(screen.getByRole("status")).toHaveTextContent("11.6700°N 78.1500°E");
    const create = screen.getByRole("button", { name: /create geofence/i });
    expect(create).toBeDisabled();

    await userEvent.click(screen.getByLabelText(/checked that this is the intended location/i));
    expect(create).toBeEnabled();
    await userEvent.click(create);
    expect(createGeofenceMock).toHaveBeenCalledTimes(1);
  });

  it("makes a latitude-first ring visibly land elsewhere, and re-requires confirmation after an edit", async () => {
    renderPanel();
    const ring = await screen.findByLabelText("New polygon ring");
    await userEvent.click(screen.getByLabelText(/checked that this is the intended location/i));

    await userEvent.clear(ring);
    // Same square typed latitude-first: valid numbers, but it is the Arctic, not Salem.
    await userEvent.paste("[[11.66,78.14],[11.66,78.16],[11.68,78.16],[11.68,78.14]]");
    expect(screen.getByRole("status")).toHaveTextContent("78.1500°N 11.6700°E");
    expect(screen.getByLabelText(/checked that this is the intended location/i)).not.toBeChecked();
    expect(screen.getByRole("button", { name: /create geofence/i })).toBeDisabled();
  });
});
