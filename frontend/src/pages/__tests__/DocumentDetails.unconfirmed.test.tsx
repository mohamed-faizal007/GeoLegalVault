import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DocumentOut } from "../../api/documents";
import DocumentDetails from "../DocumentDetails";

// REL-04 / D-049, D-050: UNCONFIRMED is informational. It is labelled and explained, an
// Administrator can clear it by the same re-verify rule as TAMPERED, and it disables nothing.

const getDocumentMock = vi.fn();
const listVersionsMock = vi.fn();
const clearIntegrityFlagMock = vi.fn();
let mockRole = "ADMINISTRATOR";

vi.mock("../../api/documents", async () => {
  const actual = await vi.importActual<typeof import("../../api/documents")>("../../api/documents");
  return {
    ...actual,
    getDocument: (...args: unknown[]) => getDocumentMock(...args),
    listVersions: (...args: unknown[]) => listVersionsMock(...args),
    clearIntegrityFlag: (...args: unknown[]) => clearIntegrityFlagMock(...args),
  };
});

vi.mock("../../context/useAuth", () => ({
  useAuth: () => ({
    user: { id: "u1", email: "u@example.com", role: mockRole },
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
  }),
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
    integrity_flag: "UNCONFIRMED",
    ...overrides,
  };
}

function renderDetails() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/documents/d-1"]}>
        <Routes>
          <Route path="/documents/:id" element={<DocumentDetails />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("an UNCONFIRMED document", () => {
  afterEach(() => {
    vi.clearAllMocks();
    mockRole = "ADMINISTRATOR";
  });

  it("is labelled, and the note says it is not proof of tampering and blocks nothing", async () => {
    getDocumentMock.mockResolvedValue(doc({}));
    renderDetails();

    expect(await screen.findByText("UNCONFIRMED")).toBeInTheDocument();
    const note = screen.getByRole("note");
    expect(note).toHaveTextContent(/not proof of tampering/);
    expect(note).toHaveTextContent(/does not block any action/);
    expect(screen.queryByText("TAMPERED")).not.toBeInTheDocument();
  });

  it("does not disable or hide the document's normal actions", async () => {
    mockRole = "LEGAL_OFFICER";
    getDocumentMock.mockResolvedValue(doc({}));
    renderDetails();

    for (const name of [/request amendment/i, /download/i, /verify/i]) {
      const button = await screen.findByRole("button", { name });
      expect(button).toBeEnabled();
    }
  });

  it("can be cleared by an Administrator, with the same reason rule, and by nobody else", async () => {
    getDocumentMock.mockResolvedValue(doc({}));
    clearIntegrityFlagMock.mockResolvedValue({
      document_id: "d-1",
      integrity_flag: null,
      verified_versions: [1],
    });
    const { unmount } = renderDetails();
    await userEvent.click(await screen.findByRole("button", { name: /clear integrity flag/i }));
    await userEvent.type(screen.getByLabelText(/reason for clearing/i), "Anchor restored after redeploy.");
    await userEvent.click(screen.getByRole("button", { name: /re-verify and clear/i }));
    expect(clearIntegrityFlagMock).toHaveBeenCalledWith("d-1", "Anchor restored after redeploy.");
    unmount();

    for (const role of ["LEGAL_OFFICER", "AUTHORIZED_STAFF", "REVIEWING_OFFICER", "AUDITOR"]) {
      mockRole = role;
      const view = renderDetails();
      await screen.findByText("Contract");
      expect(screen.queryByRole("button", { name: /clear integrity flag/i })).not.toBeInTheDocument();
      view.unmount();
    }
  });
});
