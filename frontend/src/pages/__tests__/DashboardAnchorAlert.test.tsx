import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import Dashboard from "../Dashboard";

const getAttentionMock = vi.fn();
let mockRole = "ADMINISTRATOR";

vi.mock("../../api/documents", async () => {
  const actual = await vi.importActual<typeof import("../../api/documents")>("../../api/documents");
  return {
    ...actual,
    listDocuments: () => Promise.resolve({ items: [], page: 1, limit: 5, total: 0 }),
  };
});
vi.mock("../../api/blockchain", async () => {
  const actual = await vi.importActual<typeof import("../../api/blockchain")>("../../api/blockchain");
  return { ...actual, getAnchorAttention: (...a: unknown[]) => getAttentionMock(...a) };
});
vi.mock("../../api/health", () => ({
  fetchHealth: () => Promise.resolve({ status: "ok", anchor_worker: "ok" }),
}));
vi.mock("../../context/useAuth", () => ({
  useAuth: () => ({
    user: { id: "u1", email: "me@example.com", role: mockRole },
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));
vi.mock("../../hooks/useGeoLocation", () => ({
  useGeoLocation: () => ({ coords: null, error: null, loading: false, refresh: vi.fn() }),
  getCurrentLocation: vi.fn(),
}));

const STUCK = {
  items: [
    {
      document_id: "d-1",
      title: "Vendor NDA",
      version_no: 1,
      state: "PERMANENT_FAILURE",
      last_error: "NOT_AUTHORIZED",
      attempts: 0,
      next_attempt_at: null,
      stuck_since: "2026-10-05T09:00:00Z",
      can_retry: true,
    },
  ],
  total: 1,
};

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// The whole Dashboard renders several queries; give each wait room on a loaded CI runner.
const WAIT = { timeout: 8000 };

describe("Dashboard anchor alert", () => {
  afterEach(() => {
    vi.clearAllMocks();
    mockRole = "ADMINISTRATOR";
  });

  it.each(["ADMINISTRATOR", "LEGAL_OFFICER", "AUDITOR"])("shows the alert to %s", async (role) => {
    mockRole = role;
    getAttentionMock.mockResolvedValue(STUCK);
    renderDashboard();
    expect(
      await screen.findByRole("region", { name: /waiting for blockchain anchoring/i }, WAIT),
    ).toBeInTheDocument();
    expect(screen.getByText("PERMANENT FAILURE")).toBeInTheDocument();
    expect(screen.getByText(/not authorised to anchor/i)).toBeInTheDocument();
  });

  it.each(["REVIEWING_OFFICER", "AUTHORIZED_STAFF"])(
    "does not show it to %s, and never asks the server",
    async (role) => {
      mockRole = role;
      getAttentionMock.mockResolvedValue(STUCK);
      renderDashboard();
      await screen.findByText(/no documents yet/i, undefined, WAIT);
      await waitFor(() => expect(getAttentionMock).not.toHaveBeenCalled());
      expect(screen.queryByText(/waiting for blockchain anchoring/i)).not.toBeInTheDocument();
    },
  );

  it("shows no alert on a healthy vault", async () => {
    getAttentionMock.mockResolvedValue({ items: [], total: 0 });
    renderDashboard();
    await screen.findByText(/no documents yet/i, undefined, WAIT);
    await waitFor(() => expect(getAttentionMock).toHaveBeenCalled());
    expect(screen.queryByText(/waiting for blockchain anchoring/i)).not.toBeInTheDocument();
  });
});
