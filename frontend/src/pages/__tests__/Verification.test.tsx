import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { VerifyResponse } from "../../api/verify";
import Verification from "../Verification";

const runVerifyMock = vi.fn();
const getVerifyHistoryMock = vi.fn();

vi.mock("../../api/verify", async () => {
  const actual = await vi.importActual<typeof import("../../api/verify")>("../../api/verify");
  return {
    ...actual,
    runVerify: (...args: unknown[]) => runVerifyMock(...args),
    getVerifyHistory: (...args: unknown[]) => getVerifyHistoryMock(...args),
  };
});

function renderVerification(versionId = "v-1") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/verify/${versionId}`]}>
        <Routes>
          <Route path="/verify/:versionId" element={<Verification />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function verifyResponse(overrides: Partial<VerifyResponse>): VerifyResponse {
  return {
    result: "VERIFIED",
    recomputed: "abc123",
    stored: "abc123",
    onchain: "abc123",
    tx_hash: "0xdeadbeef",
    etherscan_url: "https://sepolia.etherscan.io/tx/0xdeadbeef",
    ...overrides,
  };
}

describe("Verification page", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders a green VERIFIED banner when all three hashes agree", async () => {
    getVerifyHistoryMock.mockResolvedValue({ items: [] });
    runVerifyMock.mockResolvedValue(verifyResponse({ result: "VERIFIED" }));

    renderVerification();
    await userEvent.click(await screen.findByRole("button", { name: /run verification/i }));

    const banner = await screen.findByText("VERIFIED");
    expect(banner).toBeInTheDocument();
    expect(banner.closest("div")).toHaveClass("bg-emerald-50");
  });

  it("renders a red MISMATCH banner when the hashes disagree", async () => {
    getVerifyHistoryMock.mockResolvedValue({ items: [] });
    runVerifyMock.mockResolvedValue(
      verifyResponse({ result: "MISMATCH", recomputed: "tampered-hash" }),
    );

    renderVerification();
    await userEvent.click(await screen.findByRole("button", { name: /run verification/i }));

    const banner = await screen.findByText(/MISMATCH/);
    expect(banner).toBeInTheDocument();
    expect(banner.closest("div")).toHaveClass("bg-red-50");
  });

  it("renders a neutral NOT ANCHORED state without treating it as an error", async () => {
    getVerifyHistoryMock.mockResolvedValue({ items: [] });
    runVerifyMock.mockResolvedValue(
      verifyResponse({ result: "NOT_ANCHORED", onchain: null, tx_hash: null, etherscan_url: null }),
    );

    renderVerification();
    await userEvent.click(await screen.findByRole("button", { name: /run verification/i }));

    const banner = await screen.findByText(/NOT ANCHORED/);
    expect(banner).toBeInTheDocument();
    expect(banner.closest("div")).toHaveClass("bg-slate-50");
  });
});
