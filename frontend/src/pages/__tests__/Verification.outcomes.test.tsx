import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { VerificationRecordOut, VerifyResponse } from "../../api/verify";
import Verification from "../Verification";

// REL-04 / D-050: the three new results are worded, not only coloured, and nothing the server
// sends as free text ever reaches the page.

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

const LEAKY =
  "HTTPSConnectionPool(host='eth-sepolia.g.alchemy.com', port=443): Max retries exceeded with url: /v2/SECRETKEYABCDEF123456";

function renderVerification() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/verify/v-1"]}>
        <Routes>
          <Route path="/verify/:versionId" element={<Verification />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function response(overrides: Partial<VerifyResponse>): VerifyResponse {
  return {
    result: "VERIFIED",
    recomputed: "abc123",
    stored: "abc123",
    onchain: "abc123",
    tx_hash: null,
    etherscan_url: null,
    reason: null,
    ...overrides,
  };
}

function record(overrides: Partial<VerificationRecordOut>): VerificationRecordOut {
  return {
    id: "r-1",
    version_id: "v-1",
    requested_by: "u-1",
    recomputed_hash: "abc123",
    stored_hash: "abc123",
    onchain_hash: null,
    result: "VERIFIED",
    created_at: "2026-10-03T17:24:33Z",
    reason: null,
    ...overrides,
  };
}

async function runWith(result: VerifyResponse) {
  getVerifyHistoryMock.mockResolvedValue({ items: [] });
  runVerifyMock.mockResolvedValue(result);
  renderVerification();
  await userEvent.click(await screen.findByRole("button", { name: /run verification/i }));
  return await screen.findByRole("status");
}

describe("new verification results (D-049, D-050)", () => {
  afterEach(() => vi.clearAllMocks());

  it("CHAIN_UNREACHABLE says no result was obtained, and is not worded as not-anchored", async () => {
    const banner = await runWith(
      response({ result: "CHAIN_UNREACHABLE", onchain: null, reason: "CHAIN_TIMEOUT" }),
    );

    expect(banner).toHaveTextContent("COULD NOT CHECK THE BLOCKCHAIN");
    expect(banner).toHaveTextContent(/neither confirmed nor flagged/);
    expect(banner).toHaveTextContent("The blockchain node did not answer in time.");
    expect(banner).not.toHaveTextContent(/not anchored/i);
    expect(banner).toHaveClass("bg-amber-500/10"); // amber: not a verdict, not an alarm
  });

  it("ANCHOR_MISSING says integrity could not be confirmed and that the document was flagged", async () => {
    const banner = await runWith(
      response({ result: "ANCHOR_MISSING", onchain: null, reason: "CONTRACT_NOT_DEPLOYED" }),
    );

    expect(banner).toHaveTextContent("ANCHOR MISSING");
    expect(banner).toHaveTextContent(/integrity could not be confirmed/i);
    expect(banner).toHaveTextContent(/flagged for an administrator/i);
    expect(banner).toHaveTextContent(/No anchoring contract was found/);
    expect(banner).toHaveClass("bg-red-500/10");
    expect(banner).not.toHaveTextContent(/tamper(ed|-proof)/i); // not claimed as proven tampering
  });

  it("FILE_MISSING says the file was not found, and a null recomputed hash renders", async () => {
    const banner = await runWith(
      response({ result: "FILE_MISSING", recomputed: null, onchain: null }),
    );

    expect(banner).toHaveTextContent("STORED FILE MISSING");
    expect(banner).toHaveTextContent(/stored file for this version was not found/);
    expect(screen.getAllByText(/not available/i).length).toBeGreaterThanOrEqual(2);
  });

  it("each new result has its own icon shape, so colour is not the only cue", async () => {
    const paths = new Set<string>();
    for (const result of ["VERIFIED", "MISMATCH", "NOT_ANCHORED", "ANCHOR_MISSING", "FILE_MISSING", "CHAIN_UNREACHABLE"] as const) {
      const banner = await runWith(response({ result }));
      paths.add(banner.querySelector("path")!.getAttribute("d")!);
      document.body.innerHTML = "";
    }
    expect(paths.size).toBe(6);
  });

  it("never renders a server-supplied string: a leaky reason is replaced by a fixed sentence", async () => {
    getVerifyHistoryMock.mockResolvedValue({
      items: [record({ id: "r-2", result: "CHAIN_UNREACHABLE", reason: LEAKY })],
    });
    const leakyResponse = {
      ...response({ result: "CHAIN_UNREACHABLE", onchain: null, reason: LEAKY }),
      error: LEAKY,
      message: LEAKY,
    };
    runVerifyMock.mockResolvedValue(leakyResponse);
    renderVerification();
    await userEvent.click(await screen.findByRole("button", { name: /run verification/i }));
    const banner = await screen.findByRole("status");

    expect(banner).toHaveTextContent("The blockchain could not be read.");
    await screen.findAllByText("The blockchain could not be read."); // also in the history row
    const page = document.body.textContent ?? "";
    for (const fragment of ["SECRETKEY", "alchemy", "HTTPSConnectionPool", "Max retries", "/v2/"]) {
      expect(page).not.toContain(fragment);
    }
    expect(document.body.innerHTML).not.toContain("SECRETKEY");
  });

  it("an unrecognised result code from a newer server reads as 'could not check', never as a pass", async () => {
    const banner = await runWith(response({ result: "SOMETHING_NEW" as VerifyResponse["result"] }));

    expect(banner).toHaveTextContent("COULD NOT CHECK THE BLOCKCHAIN");
    expect(banner).not.toHaveTextContent("VERIFIED");
    expect(banner).not.toHaveTextContent(/SOMETHING_NEW/);
  });

  it("the history reads in words, including the outage between two good runs", async () => {
    getVerifyHistoryMock.mockResolvedValue({
      items: [
        record({ id: "r-3", result: "VERIFIED", created_at: "2026-10-04T10:00:37Z" }),
        record({
          id: "r-2",
          result: "CHAIN_UNREACHABLE",
          reason: "RPC_UNREACHABLE",
          created_at: "2026-10-03T17:25:40Z",
        }),
        record({ id: "r-1", result: "VERIFIED" }),
      ],
    });
    renderVerification();

    const items = await screen.findAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(within(items[1]).getByText("CHAIN UNREACHABLE")).toBeInTheDocument();
    expect(within(items[1]).getByText("The blockchain node could not be reached.")).toBeInTheDocument();
    expect(screen.queryByText(/NOT ANCHORED/)).not.toBeInTheDocument();
  });
});
