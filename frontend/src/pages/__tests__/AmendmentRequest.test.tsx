import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DocumentOut } from "../../api/documents";
import AmendmentRequest from "../AmendmentRequest";

const getDocumentMock = vi.fn();

vi.mock("../../api/documents", async () => {
  const actual = await vi.importActual<typeof import("../../api/documents")>("../../api/documents");
  return { ...actual, getDocument: (...args: unknown[]) => getDocumentMock(...args) };
});

// LocationGate depends on browser geolocation, which jsdom doesn't provide;
// these tests only care about which form renders, not the location flow.
vi.mock("../../components/LocationGate", () => ({
  default: ({ children }: { children: (coords: { lat: number; lng: number; accuracy: number }, refresh: () => void) => React.ReactNode }) =>
    children({ lat: 11.67, lng: 78.15, accuracy: 10 }, () => {}),
}));

function doc(overrides: Partial<DocumentOut>): DocumentOut {
  return {
    id: "d-1",
    title: "Contract",
    doc_type: "CONTRACT",
    classification: "RESTRICTED",
    owner_id: "u1",
    status: "ACTIVE",
    current_version_id: "v-1",
    tags: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    retention_until: null,
    integrity_flag: null,
    ...overrides,
  };
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/documents/d-1/amend"]}>
        <Routes>
          <Route path="/documents/:id/amend" element={<AmendmentRequest />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AmendmentRequest ready-for-new-version condition (item 7 / D-015, D-017)", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows the reason form (not the upload form) for ACTIVE", async () => {
    getDocumentMock.mockResolvedValue(doc({ status: "ACTIVE" }));
    renderPage();
    expect(await screen.findByText(/reason for amendment/i)).toBeInTheDocument();
    expect(screen.queryByText(/drag & drop/i)).not.toBeInTheDocument();
  });

  it("shows the upload form for AMENDMENT_REQUESTED", async () => {
    getDocumentMock.mockResolvedValue(doc({ status: "AMENDMENT_REQUESTED" }));
    renderPage();
    expect(await screen.findByText(/amendment approved for a new version/i)).toBeInTheDocument();
  });

  it("shows the upload form for DRAFT with review_feedback (changes requested)", async () => {
    getDocumentMock.mockResolvedValue(
      doc({
        status: "DRAFT",
        review_feedback: { comment: "fix clause 4", reviewed_at: "2026-02-01T10:00:00Z" },
      }),
    );
    renderPage();
    expect(await screen.findByText(/changes were requested/i)).toBeInTheDocument();
  });

  it("shows the reason form, not the upload form, for a fresh DRAFT with no review_feedback", async () => {
    getDocumentMock.mockResolvedValue(doc({ status: "DRAFT", review_feedback: null }));
    renderPage();
    expect(await screen.findByText(/reason for amendment/i)).toBeInTheDocument();
  });
});
