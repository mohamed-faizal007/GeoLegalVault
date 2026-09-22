import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import AdminPanel from "../AdminPanel";

let mockRole = "ADMINISTRATOR";

vi.mock("../../context/useAuth", () => ({
  useAuth: () => ({
    user: { id: "u1", email: "user@example.com", role: mockRole },
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock("../../components/admin/UserManagementPanel", () => ({
  default: () => <p>users panel</p>,
}));
vi.mock("../../components/admin/GeofenceManagementPanel", () => ({
  default: () => <p>geofences panel</p>,
}));
vi.mock("../../components/admin/ReportsPanel", () => ({
  default: () => <p>reports panel</p>,
}));
vi.mock("../../components/admin/HealthPanel", () => ({
  default: () => <p>health panel</p>,
}));

describe("AdminPanel tab gating", () => {
  it("Administrator sees all four tabs, defaulting to Users", () => {
    mockRole = "ADMINISTRATOR";
    render(<AdminPanel />);

    for (const label of ["Users", "Geofences", "Reports", "System Health"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
    expect(screen.getByText("users panel")).toBeInTheDocument();
  });

  it("Auditor sees only the Reports tab, and it's shown by default", () => {
    mockRole = "AUDITOR";
    render(<AdminPanel />);

    expect(screen.getByRole("button", { name: "Reports" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Users" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Geofences" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "System Health" })).not.toBeInTheDocument();
    expect(screen.getByText("reports panel")).toBeInTheDocument();
  });

  it("clicking a tab switches the visible panel", async () => {
    mockRole = "ADMINISTRATOR";
    render(<AdminPanel />);

    await userEvent.click(screen.getByRole("button", { name: "Reports" }));
    expect(screen.getByText("reports panel")).toBeInTheDocument();
    expect(screen.queryByText("users panel")).not.toBeInTheDocument();
  });
});
