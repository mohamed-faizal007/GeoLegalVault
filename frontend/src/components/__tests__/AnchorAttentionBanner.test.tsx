import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AnchorAttentionItem } from "../../api/blockchain";
import { ApiError } from "../../api/http";
import AnchorAttentionBanner from "../AnchorAttentionBanner";

const getAttentionMock = vi.fn();
const retryMock = vi.fn();
const healthMock = vi.fn();
const locationMock = vi.fn();
let mockRole = "ADMINISTRATOR";

vi.mock("../../api/blockchain", async () => {
  const actual = await vi.importActual<typeof import("../../api/blockchain")>("../../api/blockchain");
  return {
    ...actual,
    getAnchorAttention: (...a: unknown[]) => getAttentionMock(...a),
    retryAnchor: (...a: unknown[]) => retryMock(...a),
  };
});
vi.mock("../../api/health", () => ({ fetchHealth: (...a: unknown[]) => healthMock(...a) }));
vi.mock("../../context/useAuth", () => ({
  useAuth: () => ({
    user: { id: "u1", email: "u@example.com", role: mockRole },
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));
vi.mock("../../hooks/useGeoLocation", () => ({
  getCurrentLocation: (...a: unknown[]) => locationMock(...a),
}));

const COORDS = { lat: 11.67, lng: 78.15, accuracy: 10, timestamp: 1_700_000_000 };

function item(overrides: Partial<AnchorAttentionItem> = {}): AnchorAttentionItem {
  return {
    document_id: "d-1",
    title: "Vendor NDA",
    version_no: 1,
    state: "RETRYING",
    last_error: "RPC_UNREACHABLE",
    attempts: 2,
    next_attempt_at: "2026-10-05T10:00:00Z",
    stuck_since: "2026-10-05T09:00:00Z",
    can_retry: true,
    ...overrides,
  };
}

function renderBanner() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AnchorAttentionBanner />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function withItems(...items: AnchorAttentionItem[]) {
  getAttentionMock.mockResolvedValue({ items, total: items.length });
}

describe("AnchorAttentionBanner", () => {
  beforeEach(() => {
    healthMock.mockResolvedValue({ status: "ok", anchor_worker: "ok" });
    locationMock.mockResolvedValue(COORDS);
  });
  afterEach(() => {
    vi.clearAllMocks();
    mockRole = "ADMINISTRATOR";
  });

  it.each(["REVIEWING_OFFICER", "AUTHORIZED_STAFF"])(
    "renders nothing, and asks the server nothing, for %s (no anchor:view)",
    (role) => {
      mockRole = role;
      withItems(item());
      const { container } = renderBanner();
      expect(container).toBeEmptyDOMElement();
      expect(getAttentionMock).not.toHaveBeenCalled();
    },
  );

  it("renders nothing when every approved document is anchored", async () => {
    withItems();
    const { container } = renderBanner();
    await waitFor(() => expect(getAttentionMock).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it.each([
    ["RETRYING", "RETRYING", /retrying automatically/i],
    ["AWAITING_CONFIRMATION", "AWAITING CONFIRMATION", /waiting for the network to confirm/i],
    ["PERMANENT_FAILURE", "PERMANENT FAILURE", /automatic retries have stopped/i],
    ["NEEDS_ADMIN_RETRY", "NEEDS ADMIN RETRY", /too long to retry automatically/i],
  ] as const)("states %s in words, not only colour", async (state, badge, sentence) => {
    withItems(item({ state }));
    renderBanner();
    expect(await screen.findByText(badge)).toBeInTheDocument();
    expect(screen.getByText(sentence)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /waiting for blockchain anchoring/i })).toBeInTheDocument();
  });

  it("says plainly that an administrator must act, to roles that cannot retry", async () => {
    mockRole = "AUDITOR";
    withItems(item({ state: "PERMANENT_FAILURE", can_retry: false }));
    renderBanner();
    expect(await screen.findByText(/an administrator needs to request a retry/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /retry anchoring/i })).not.toBeInTheDocument();
  });

  it("never prints raw error text or RPC details, only a fixed code's sentence", async () => {
    const leaky = "HTTPSConnectionPool(host='eth-sepolia.g.alchemy.com'): url: /v2/SECRETKEY123456";
    withItems(
      item({ document_id: "d-1", last_error: leaky }),
      item({ document_id: "d-2", title: "Other", last_error: "RPC_UNREACHABLE" }),
    );
    renderBanner();
    expect(await screen.findByText(/the blockchain network could not be reached/i)).toBeInTheDocument();
    expect(screen.getByText(/\(code RPC_UNREACHABLE\)/)).toBeInTheDocument();
    expect(screen.getByText(/anchoring has not completed/i)).toBeInTheDocument();

    const text = document.body.textContent ?? "";
    for (const forbidden of ["SECRETKEY", "alchemy", "HTTPSConnectionPool", "/v2/", "sha256"]) {
      expect(text).not.toContain(forbidden);
    }
  });

  it("warns when no anchor worker is running, since a retry only re-queues", async () => {
    healthMock.mockResolvedValue({ status: "ok", anchor_worker: "stale" });
    withItems(item());
    renderBanner();
    expect(await screen.findByText(/anchor worker does not appear to be running/i)).toBeInTheDocument();
  });

  it("does not warn when the worker is healthy", async () => {
    withItems(item());
    renderBanner();
    await screen.findByText("RETRYING");
    await waitFor(() => expect(healthMock).toHaveBeenCalled());
    expect(screen.queryByText(/anchor worker does not appear/i)).not.toBeInTheDocument();
  });

  describe("the Administrator retry", () => {
    it("is offered for stuck states, but not while a transaction is awaiting confirmation", async () => {
      withItems(
        item({ document_id: "d-1", title: "Stuck", state: "PERMANENT_FAILURE" }),
        item({ document_id: "d-2", title: "In flight", state: "AWAITING_CONFIRMATION" }),
      );
      renderBanner();
      await screen.findByText("Stuck");
      expect(screen.getAllByRole("button", { name: /retry anchoring/i })).toHaveLength(1);
    });

    it("is hidden when the server says this caller cannot retry", async () => {
      withItems(item({ state: "PERMANENT_FAILURE", can_retry: false }));
      renderBanner();
      await screen.findByText("PERMANENT FAILURE");
      expect(screen.queryByRole("button", { name: /retry anchoring/i })).not.toBeInTheDocument();
    });

    it("needs a reason of at least 10 characters, then sends it with the location", async () => {
      const user = userEvent.setup();
      withItems(item({ state: "PERMANENT_FAILURE" }));
      retryMock.mockResolvedValue({ document_id: "d-1", state: "RETRYING", next_attempt_at: null });
      renderBanner();

      await user.click(await screen.findByRole("button", { name: /retry anchoring/i }));
      const send = screen.getByRole("button", { name: /send retry request/i });
      expect(send).toBeDisabled();

      await user.type(screen.getByLabelText(/reason for the retry/i), "too short");
      expect(send).toBeDisabled();
      await user.type(screen.getByLabelText(/reason for the retry/i), "  wallet funded again  ");
      expect(send).toBeEnabled();

      await user.click(send);
      await waitFor(() => expect(retryMock).toHaveBeenCalledTimes(1));
      expect(retryMock).toHaveBeenCalledWith("d-1", "too short  wallet funded again", COORDS);

      expect(await screen.findByText(/retry requested for .*vendor nda/i)).toBeInTheDocument();
      expect(screen.queryByLabelText(/reason for the retry/i)).not.toBeInTheDocument();
      await waitFor(() => expect(getAttentionMock).toHaveBeenCalledTimes(2)); // re-fetched
    });

    it("explains that it only re-queues, and that the reason is audited", async () => {
      const user = userEvent.setup();
      withItems(item({ state: "NEEDS_ADMIN_RETRY" }));
      renderBanner();
      await user.click(await screen.findByRole("button", { name: /retry anchoring/i }));
      expect(screen.getByText(/only puts the anchor back in the queue/i)).toBeInTheDocument();
      expect(screen.getByText(/written to the audit log/i)).toBeInTheDocument();
    });

    it("can be cancelled without calling the server", async () => {
      const user = userEvent.setup();
      withItems(item({ state: "PERMANENT_FAILURE" }));
      renderBanner();
      await user.click(await screen.findByRole("button", { name: /retry anchoring/i }));
      await user.click(screen.getByRole("button", { name: /cancel/i }));
      expect(screen.queryByLabelText(/reason for the retry/i)).not.toBeInTheDocument();
      expect(retryMock).not.toHaveBeenCalled();
    });

    it("shows the server's refusal as a plain-language error and keeps the form", async () => {
      const user = userEvent.setup();
      withItems(item({ state: "PERMANENT_FAILURE" }));
      retryMock.mockRejectedValue(new ApiError(409, "ANCHOR_NOT_RETRYABLE", "raw server text"));
      renderBanner();

      await user.click(await screen.findByRole("button", { name: /retry anchoring/i }));
      await user.type(screen.getByLabelText(/reason for the retry/i), "wallet funded again");
      await user.click(screen.getByRole("button", { name: /send retry request/i }));

      const alert = await screen.findByRole("alert");
      expect(within(alert).getByText(/can't be re-queued right now/i)).toBeInTheDocument();
      expect(within(alert).getByText(/ANCHOR_NOT_RETRYABLE/)).toBeInTheDocument();
      expect(screen.getByLabelText(/reason for the retry/i)).toBeInTheDocument();
    });

    it("does not call the server if location access fails", async () => {
      const user = userEvent.setup();
      withItems(item({ state: "PERMANENT_FAILURE" }));
      locationMock.mockRejectedValue(new Error("Location access was denied."));
      renderBanner();

      await user.click(await screen.findByRole("button", { name: /retry anchoring/i }));
      await user.type(screen.getByLabelText(/reason for the retry/i), "wallet funded again");
      await user.click(screen.getByRole("button", { name: /send retry request/i }));

      expect(await screen.findByText(/location access was denied/i)).toBeInTheDocument();
      expect(retryMock).not.toHaveBeenCalled();
    });
  });
});
