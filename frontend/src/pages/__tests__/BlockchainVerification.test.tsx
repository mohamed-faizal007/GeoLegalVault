import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AnchorOut } from "../../api/blockchain";
import { compareHashes } from "../../lib/hashCompare";
import BlockchainVerification from "../BlockchainVerification";

const getAnchorMock = vi.fn();
vi.mock("../../api/blockchain", async () => {
  const actual = await vi.importActual<typeof import("../../api/blockchain")>("../../api/blockchain");
  return { ...actual, getAnchor: (...a: unknown[]) => getAnchorMock(...a) };
});

const HASH = "ab".repeat(32);
const TX = "0x" + "cd".repeat(32);

function anchor(overrides: Partial<AnchorOut> = {}): AnchorOut {
  return {
    id: "a1",
    document_id: "d1",
    version_id: "v1",
    sha256: HASH,
    event_type: 1,
    tx_hash: TX,
    block_number: 7,
    contract_address: "0x" + "11".repeat(20),
    network: "sepolia",
    network_label: "Sepolia testnet",
    chain_id: 11155111,
    status: "CONFIRMED",
    created_at: "2026-10-01T10:00:00Z",
    confirmed_at: "2026-10-01T10:01:00Z",
    etherscan_url: `https://sepolia.etherscan.io/tx/${TX}`,
    onchain: { hash: "0x" + HASH, event_type: 1, ts: 1_700_000_000, exists: true },
    error: null,
    ...overrides,
  };
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/blockchain/v1"]}>
        <Routes>
          <Route path="/blockchain/:versionId" element={<BlockchainVerification />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("compareHashes", () => {
  it("ignores the 0x prefix and case, and tells the four outcomes apart", () => {
    expect(compareHashes(anchor())).toBe("MATCH");
    expect(compareHashes(anchor({ sha256: HASH.toUpperCase() }))).toBe("MATCH");
    expect(compareHashes(anchor({ onchain: { hash: "0x" + "00".repeat(32), event_type: 1, ts: 1, exists: true } }))).toBe(
      "MISMATCH",
    );
    expect(compareHashes(anchor({ onchain: { hash: "0x" + "00".repeat(32), event_type: 1, ts: 0, exists: false } }))).toBe(
      "NOT_ON_CHAIN",
    );
    expect(compareHashes(anchor({ onchain: null }))).toBe("UNAVAILABLE");
  });
});

describe("Blockchain Anchor Record", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows both hashes together with 'Match' in words, and the network", async () => {
    getAnchorMock.mockResolvedValue(anchor());
    renderPage();
    expect(await screen.findByTestId("hash-comparison")).toHaveTextContent("Match");
    expect(screen.getByText("Recorded hash (database)")).toBeInTheDocument();
    expect(screen.getByText("On-chain hash (read live)")).toBeInTheDocument();
    expect(screen.getByText(HASH)).toBeInTheDocument();
    expect(screen.getByText("0x" + HASH)).toBeInTheDocument();
    expect(screen.getAllByText("Sepolia testnet").length).toBeGreaterThan(0);
  });

  it("says 'Mismatch' in words, not by colour alone", async () => {
    getAnchorMock.mockResolvedValue(
      anchor({ onchain: { hash: "0x" + "00".repeat(32), event_type: 1, ts: 1, exists: true } }),
    );
    renderPage();
    expect(await screen.findByTestId("hash-comparison")).toHaveTextContent("Mismatch");
    expect(screen.getByText(/differs from the hash on the chain/i)).toBeInTheDocument();
  });

  it("says the hashes were not compared when the chain could not be read", async () => {
    getAnchorMock.mockResolvedValue(anchor({ onchain: null }));
    renderPage();
    expect(await screen.findByTestId("hash-comparison")).toHaveTextContent("Not compared");
    expect(screen.getByText("— not read —")).toBeInTheDocument();
  });

  it("links the transaction on Etherscan and copies the hash", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    getAnchorMock.mockResolvedValue(anchor());
    renderPage();
    const link = await screen.findByRole("link", { name: /view on etherscan \(sepolia testnet\)/i });
    expect(link).toHaveAttribute("href", `https://sepolia.etherscan.io/tx/${TX}`);
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    await userEvent.click(screen.getByRole("button", { name: /copy transaction hash/i }));
    expect(writeText).toHaveBeenCalledWith(TX);
    expect(await screen.findByText("Copied")).toBeInTheDocument();
  });

  it("offers no explorer link on a chain that is not Sepolia, and says so", async () => {
    getAnchorMock.mockResolvedValue(
      anchor({ etherscan_url: null, network_label: "Chain 31337 (not Sepolia; no block explorer)", chain_id: 31337 }),
    );
    renderPage();
    expect(await screen.findByText(/no block explorer link/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /etherscan/i })).not.toBeInTheDocument();
  });
});
