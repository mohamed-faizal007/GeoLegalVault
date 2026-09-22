import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import UserManagementPanel from "../UserManagementPanel";

const listUsersMock = vi.fn();
const listGeofencesMock = vi.fn();
const updateUserMock = vi.fn();

vi.mock("../../../api/users", async () => {
  const actual = await vi.importActual<typeof import("../../../api/users")>("../../../api/users");
  return {
    ...actual,
    listUsers: (...a: unknown[]) => listUsersMock(...a),
    updateUser: (...a: unknown[]) => updateUserMock(...a),
  };
});
vi.mock("../../../api/geofences", async () => {
  const actual =
    await vi.importActual<typeof import("../../../api/geofences")>("../../../api/geofences");
  return { ...actual, listGeofences: (...a: unknown[]) => listGeofencesMock(...a) };
});
vi.mock("../../../context/useAuth", () => ({
  useAuth: () => ({
    user: { id: "admin-1", email: "admin@example.com", role: "ADMINISTRATOR" },
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

const user = (over: Record<string, unknown>) => ({
  id: "u-1",
  email: "staff@example.com",
  name: "Staff",
  role: "AUTHORIZED_STAFF",
  assigned_geofence_ids: [],
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  last_login: null,
  ...over,
});

function renderPanel(users: unknown[]) {
  listUsersMock.mockResolvedValue({ items: users, page: 1, limit: 100, total: users.length });
  listGeofencesMock.mockResolvedValue({
    items: [
      { id: "g-1", name: "HQ", region: { type: "Polygon", coordinates: [[]] }, active: true },
      { id: "g-2", name: "Annex", region: { type: "Polygon", coordinates: [[]] }, active: true },
    ],
    page: 1,
    limit: 100,
    total: 2,
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <UserManagementPanel />
    </QueryClientProvider>,
  );
}

describe("UserManagementPanel editing", () => {
  afterEach(() => vi.clearAllMocks());

  it("warns when a user has no assigned geofence and names the ones they have", async () => {
    renderPanel([
      user({ id: "u-1", email: "none@example.com" }),
      user({ id: "u-2", email: "some@example.com", assigned_geofence_ids: ["g-1"] }),
    ]);
    expect(await screen.findByText("No geofence")).toBeInTheDocument();
    // "HQ" also appears as an <option> in the create form, so scope to the table cell.
    const row = screen.getByText("some@example.com").closest("tr")!;
    await within(row).findByText("HQ");
  });

  it("saves name, role and geofences through PATCH", async () => {
    updateUserMock.mockResolvedValue(user({}));
    renderPanel([user({})]);

    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    const name = screen.getByLabelText("Full name");
    await userEvent.clear(name);
    await userEvent.type(name, "New Name");
    await userEvent.selectOptions(screen.getByLabelText("Role"), "AUDITOR");
    await userEvent.selectOptions(screen.getByLabelText("Assigned geofences"), ["g-1", "g-2"]);
    await userEvent.click(screen.getByRole("button", { name: /save changes/i }));

    expect(updateUserMock).toHaveBeenCalledWith("u-1", {
      name: "New Name",
      role: "AUDITOR",
      assigned_geofence_ids: ["g-1", "g-2"],
    });
  });

  it("disables role change and self-deactivation on the admin's own row", async () => {
    renderPanel([user({ id: "admin-1", email: "admin@example.com", role: "ADMINISTRATOR" })]);
    const row = (await screen.findByText("admin@example.com")).closest("tr")!;
    expect(within(row).getByRole("button", { name: "Deactivate" })).toBeDisabled();

    await userEvent.click(within(row).getByRole("button", { name: "Edit" }));
    expect(screen.getByLabelText("Role")).toBeDisabled();
  });
});
