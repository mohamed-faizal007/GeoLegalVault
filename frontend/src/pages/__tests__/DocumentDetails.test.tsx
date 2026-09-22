import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DocumentOut } from "../../api/documents";
import DocumentDetails from "../DocumentDetails";

const getDocumentMock = vi.fn();
const listVersionsMock = vi.fn();
let mockRole = "LEGAL_OFFICER";

vi.mock("../../api/documents", async () => {
  const actual = await vi.importActual<typeof import("../../api/documents")>("../../api/documents");
  return {
    ...actual,
    getDocument: (...args: unknown[]) => getDocumentMock(...args),
    listVersions: (...args: unknown[]) => listVersionsMock(...args),
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
    integrity_flag: null,
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

describe("DocumentDetails action buttons", () => {
  afterEach(() => {
    vi.clearAllMocks();
    mockRole = "LEGAL_OFFICER";
  });

  it("offers 'Upload amended version' when AMENDMENT_REQUESTED", async () => {
    getDocumentMock.mockResolvedValue(doc({ status: "AMENDMENT_REQUESTED" }));
    renderDetails();
    expect(await screen.findByRole("button", { name: /upload amended version/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /request amendment/i })).not.toBeInTheDocument();
  });

  it("hides 'Upload amended version' from roles without document:amend", async () => {
    mockRole = "AUDITOR";
    getDocumentMock.mockResolvedValue(doc({ status: "AMENDMENT_REQUESTED" }));
    renderDetails();
    await screen.findByText("Contract");
    expect(screen.queryByRole("button", { name: /upload amended version/i })).not.toBeInTheDocument();
  });

  it("shows Archive for ACTIVE but not SUPERSEDED (backend only archives ACTIVE)", async () => {
    getDocumentMock.mockResolvedValue(doc({ status: "ACTIVE" }));
    const { unmount } = renderDetails();
    expect(await screen.findByRole("button", { name: /^archive$/i })).toBeInTheDocument();
    unmount();

    getDocumentMock.mockResolvedValue(doc({ status: "SUPERSEDED" }));
    renderDetails();
    await screen.findByText("Contract");
    expect(screen.queryByRole("button", { name: /^archive$/i })).not.toBeInTheDocument();
  });
});

function version(over: Record<string, unknown>) {
  return {
    id: "v-1",
    document_id: "d-1",
    version_no: 1,
    sha256: "abc",
    prev_version_hash: null,
    storage_key: "k",
    size_bytes: 1,
    mime: "application/pdf",
    status: "PENDING_APPROVAL",
    uploaded_by: "someone-else",
    uploaded_at: "2026-01-01T00:00:00Z",
    anchored: false,
    anchor_id: null,
    ...over,
  };
}

describe("maker-checker buttons", () => {
  afterEach(() => {
    vi.clearAllMocks();
    mockRole = "LEGAL_OFFICER";
  });

  it("hides Approve, with an explanation, when the current user uploaded the version", async () => {
    getDocumentMock.mockResolvedValue(doc({ status: "PENDING_APPROVAL", owner_id: "someone-else" }));
    listVersionsMock.mockResolvedValue({ items: [version({ uploaded_by: "u1" })] });
    renderDetails();
    expect(await screen.findByText(/you uploaded this version/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^approve$/i })).not.toBeInTheDocument();
  });

  it("shows Approve when someone else uploaded the version", async () => {
    getDocumentMock.mockResolvedValue(doc({ status: "PENDING_APPROVAL", owner_id: "someone-else" }));
    listVersionsMock.mockResolvedValue({ items: [version({ uploaded_by: "someone-else" })] });
    renderDetails();
    expect(await screen.findByRole("button", { name: /^approve$/i })).toBeInTheDocument();
  });

  it("judges by the highest version, not the owner (amendment by another user)", async () => {
    // Document owned by u1, but V2 was uploaded by another user: u1 may approve V2.
    getDocumentMock.mockResolvedValue(doc({ status: "PENDING_APPROVAL", owner_id: "u1" }));
    listVersionsMock.mockResolvedValue({
      items: [
        version({ id: "v-1", version_no: 1, uploaded_by: "u1" }),
        version({ id: "v-2", version_no: 2, uploaded_by: "other" }),
      ],
    });
    renderDetails();
    expect(await screen.findByRole("button", { name: /^approve$/i })).toBeInTheDocument();
  });

  it("fails closed: no Approve button while versions have not loaded", async () => {
    getDocumentMock.mockResolvedValue(doc({ status: "PENDING_APPROVAL" }));
    listVersionsMock.mockReturnValue(new Promise(() => {}));
    renderDetails();
    await screen.findByText("Contract");
    expect(screen.queryByRole("button", { name: /^approve$/i })).not.toBeInTheDocument();
  });

  it("hides Review for the uploader and shows it for another reviewer", async () => {
    mockRole = "REVIEWING_OFFICER";
    getDocumentMock.mockResolvedValue(doc({ status: "SUBMITTED", owner_id: "x" }));
    listVersionsMock.mockResolvedValue({ items: [version({ uploaded_by: "x", status: "SUBMITTED" })] });
    renderDetails();
    expect(await screen.findByRole("button", { name: /^review$/i })).toBeInTheDocument();
  });
});

describe("reviewer feedback", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows the reviewer's comment on a DRAFT that came back with changes requested", async () => {
    getDocumentMock.mockResolvedValue(
      doc({
        status: "DRAFT",
        review_feedback: { comment: "fix clause 4", reviewed_at: "2026-02-01T10:00:00Z" },
      }),
    );
    listVersionsMock.mockResolvedValue({ items: [version({ uploaded_by: "u1" })] });
    renderDetails();
    expect(await screen.findByText("fix clause 4")).toBeInTheDocument();
    expect(screen.getByText(/changes requested/i)).toBeInTheDocument();
  });

  it("shows no feedback note when there is none", async () => {
    getDocumentMock.mockResolvedValue(doc({ status: "DRAFT", review_feedback: null }));
    listVersionsMock.mockResolvedValue({ items: [version({ uploaded_by: "u1" })] });
    renderDetails();
    await screen.findByText("Contract");
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });
});

describe("A2: corrected-file upload and current-version-uploader submit (item 7)", () => {
  afterEach(() => {
    vi.clearAllMocks();
    mockRole = "LEGAL_OFFICER";
  });

  it("offers 'Upload corrected file' on a DRAFT with changes requested, not a fresh DRAFT", async () => {
    getDocumentMock.mockResolvedValue(
      doc({
        status: "DRAFT",
        review_feedback: { comment: "fix clause 4", reviewed_at: "2026-02-01T10:00:00Z" },
      }),
    );
    listVersionsMock.mockResolvedValue({ items: [version({ uploaded_by: "u1" })] });
    renderDetails();
    expect(await screen.findByRole("button", { name: /upload corrected file/i })).toBeInTheDocument();
  });

  it("hides 'Upload corrected file' on a fresh DRAFT with no review_feedback", async () => {
    getDocumentMock.mockResolvedValue(doc({ status: "DRAFT", review_feedback: null }));
    listVersionsMock.mockResolvedValue({ items: [version({ uploaded_by: "u1" })] });
    renderDetails();
    await screen.findByText("Contract");
    expect(screen.queryByRole("button", { name: /upload corrected file/i })).not.toBeInTheDocument();
  });

  it("shows Submit for review only for the current version's uploader, with an explanation otherwise", async () => {
    getDocumentMock.mockResolvedValue(doc({ status: "DRAFT", owner_id: "u1" }));
    listVersionsMock.mockResolvedValue({ items: [version({ uploaded_by: "other" })] });
    renderDetails();
    expect(await screen.findByText(/only whoever uploaded the current version/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /submit for review/i })).not.toBeInTheDocument();
  });

  it("shows Submit for review for a non-owner who is the current version's uploader", async () => {
    getDocumentMock.mockResolvedValue(doc({ status: "DRAFT", owner_id: "someone-else" }));
    listVersionsMock.mockResolvedValue({ items: [version({ uploaded_by: "u1" })] });
    renderDetails();
    expect(await screen.findByRole("button", { name: /submit for review/i })).toBeInTheDocument();
  });
});
