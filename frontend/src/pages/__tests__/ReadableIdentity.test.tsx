import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AuditLogOut } from "../../api/audit";
import type { DocumentOut } from "../../api/documents";
import AuditLogs from "../AuditLogs";
import Dashboard from "../Dashboard";
import DocumentDetails from "../DocumentDetails";

const listAuditLogsMock = vi.fn();
const listAuditActionsMock = vi.fn();
const getDocumentMock = vi.fn();
const listDocumentsMock = vi.fn();
let mockUser: { id: string; email: string; role: string; name?: string } = {
  id: "u1",
  email: "me@example.com",
  role: "AUDITOR",
};

vi.mock("../../api/audit", async () => {
  const actual = await vi.importActual<typeof import("../../api/audit")>("../../api/audit");
  return {
    ...actual,
    listAuditLogs: (...a: unknown[]) => listAuditLogsMock(...a),
    listAuditActions: (...a: unknown[]) => listAuditActionsMock(...a),
  };
});
vi.mock("../../api/documents", async () => {
  const actual = await vi.importActual<typeof import("../../api/documents")>("../../api/documents");
  return {
    ...actual,
    getDocument: (...a: unknown[]) => getDocumentMock(...a),
    listDocuments: (...a: unknown[]) => listDocumentsMock(...a),
    listVersions: () => Promise.resolve({ items: [] }),
  };
});
vi.mock("../../api/health", () => ({ fetchHealth: () => Promise.resolve({ anchor_worker: "ok" }) }));
vi.mock("../../hooks/useGeoLocation", () => ({
  useGeoLocation: () => ({ coords: null, error: null, loading: false, refresh: vi.fn() }),
  getCurrentLocation: vi.fn(),
}));
vi.mock("../../context/useAuth", () => ({
  useAuth: () => ({ user: mockUser, isLoading: false, login: vi.fn(), logout: vi.fn() }),
}));

const OWNER_ID = "665f00000000000000000001";
const DOC_ID = "665f000000000000000000d1";

function row(overrides: Partial<AuditLogOut> = {}): AuditLogOut {
  return {
    id: "a-1",
    actor_id: OWNER_ID,
    actor_label: "Olivia Owner",
    actor_email: "owner@example.com",
    action: "DOCUMENT_UPLOAD",
    target_type: "document",
    target_id: DOC_ID,
    target_label: "Approval Demo",
    result: "SUCCESS",
    ip: null,
    location: null,
    meta: {},
    redacted: false,
    created_at: "2026-03-10T12:00:00Z",
    ...overrides,
  };
}

function wrap(path: string, routes: React.ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>{routes}</Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const lastAuditCall = () => listAuditLogsMock.mock.calls.at(-1)![0];

describe("Audit Logs: readable names (A)", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows the actor's name and the document title, with the ids as secondary text", async () => {
    listAuditActionsMock.mockResolvedValue({ actions: ["DOCUMENT_UPLOAD", "LOGIN_SUCCESS"] });
    listAuditLogsMock.mockResolvedValue({ items: [row()], page: 1, limit: 25, total: 1 });
    wrap("/audit", <Route path="/audit" element={<AuditLogs />} />);

    expect(await screen.findByRole("button", { name: "Olivia Owner" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approval Demo" })).toBeInTheDocument();
    expect(screen.getByText(OWNER_ID)).toBeInTheDocument();
    expect(screen.getByText(DOC_ID)).toBeInTheDocument();
  });

  it("marks an actor whose account no longer exists, and keeps the id as the filter label", async () => {
    listAuditActionsMock.mockResolvedValue({ actions: [] });
    listAuditLogsMock.mockResolvedValue({
      items: [row({ actor_label: null, actor_email: null, target_label: null })],
      page: 1,
      limit: 25,
      total: 1,
    });
    wrap("/audit", <Route path="/audit" element={<AuditLogs />} />);

    expect(await screen.findByText("Unknown user")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: OWNER_ID })).toBeInTheDocument();
    // A target above the viewer's clearance has no title: only the id is shown.
    expect(screen.getByRole("button", { name: DOC_ID })).toBeInTheDocument();
    expect(screen.queryByText("Approval Demo")).not.toBeInTheDocument();
  });
});

describe("Audit Logs: filters (B)", () => {
  afterEach(() => vi.clearAllMocks());

  it("offers the real actions in a dropdown and sends the choice to the server", async () => {
    listAuditActionsMock.mockResolvedValue({ actions: ["ACCESS_DENIED", "LOGIN_SUCCESS"] });
    listAuditLogsMock.mockResolvedValue({ items: [row()], page: 1, limit: 25, total: 1 });
    wrap("/audit", <Route path="/audit" element={<AuditLogs />} />);

    await screen.findByRole("button", { name: "Olivia Owner" });
    await userEvent.selectOptions(await screen.findByLabelText("Action"), "ACCESS_DENIED");
    await waitFor(() => expect(lastAuditCall()).toEqual(expect.objectContaining({ action: "ACCESS_DENIED" })));
  });

  it("searches actors by name, from two characters", async () => {
    listAuditActionsMock.mockResolvedValue({ actions: [] });
    listAuditLogsMock.mockResolvedValue({ items: [row()], page: 1, limit: 25, total: 1 });
    wrap("/audit", <Route path="/audit" element={<AuditLogs />} />);

    await screen.findByRole("button", { name: "Olivia Owner" });
    await userEvent.type(screen.getByLabelText(/actor \(name or email\)/i), "o");
    expect(lastAuditCall().actor).toBeUndefined(); // one character is not sent
    await userEvent.type(screen.getByLabelText(/actor \(name or email\)/i), "l");
    await waitFor(() => expect(lastAuditCall()).toEqual(expect.objectContaining({ actor: "ol" })));
  });

  it("finds a document by title, filters its history, and keeps paging with the filter", async () => {
    listAuditActionsMock.mockResolvedValue({ actions: [] });
    listAuditLogsMock.mockResolvedValue({ items: [row()], page: 1, limit: 25, total: 60 });
    listDocumentsMock.mockResolvedValue({
      items: [{ id: DOC_ID, title: "Approval Demo" }],
      page: 1,
      limit: 6,
      total: 1,
    });
    getDocumentMock.mockResolvedValue({ id: DOC_ID, title: "Approval Demo" });
    wrap("/audit", <Route path="/audit" element={<AuditLogs />} />);

    await screen.findByRole("button", { name: "Olivia Owner" });
    await userEvent.type(screen.getByLabelText(/document \(find by title\)/i), "appr");
    const results = await screen.findByRole("list", { name: "Matching documents" });
    await userEvent.click(within(results).getByRole("button", { name: "Approval Demo" }));
    await waitFor(() => expect(lastAuditCall()).toEqual(expect.objectContaining({ document_id: DOC_ID })));
    expect(await screen.findByText(/and its versions/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() =>
      expect(lastAuditCall()).toEqual(expect.objectContaining({ document_id: DOC_ID, page: 2 })),
    );

    await userEvent.click(screen.getByRole("button", { name: /clear filters/i }));
    await waitFor(() => expect(lastAuditCall().document_id).toBeUndefined());
    expect(lastAuditCall().page).toBe(1);
  });

  it("opens from a document's 'View audit trail' link already filtered", async () => {
    listAuditActionsMock.mockResolvedValue({ actions: [] });
    listAuditLogsMock.mockResolvedValue({ items: [row()], page: 1, limit: 25, total: 1 });
    getDocumentMock.mockResolvedValue({ id: DOC_ID, title: "Approval Demo" });
    wrap(`/audit?document_id=${DOC_ID}`, <Route path="/audit" element={<AuditLogs />} />);
    await screen.findByRole("button", { name: "Olivia Owner" });
    expect(lastAuditCall()).toEqual(expect.objectContaining({ document_id: DOC_ID }));
    expect(await screen.findByText("Approval Demo", { selector: "strong" })).toBeInTheDocument();
  });
});

function doc(overrides: Partial<DocumentOut> = {}): DocumentOut {
  return {
    id: DOC_ID,
    title: "Approval Demo",
    doc_type: "CONTRACT",
    classification: "INTERNAL",
    owner_id: OWNER_ID,
    owner_name: "Olivia Owner",
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

describe("Document page owner (A)", () => {
  afterEach(() => {
    vi.clearAllMocks();
    mockUser = { id: "u1", email: "me@example.com", role: "AUDITOR" };
  });

  it("shows the owner's name with the id beside it, and links the audit trail to auditors", async () => {
    getDocumentMock.mockResolvedValue(doc());
    wrap("/documents/d", <Route path="/documents/:id" element={<DocumentDetails />} />);
    expect(await screen.findByText("Olivia Owner")).toBeInTheDocument();
    expect(screen.getByText(OWNER_ID)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view audit trail/i })).toHaveAttribute(
      "href",
      `/audit?document_id=${DOC_ID}`,
    );
  });

  it("says 'Unknown user' when the owner account is gone, and hides the audit link from staff", async () => {
    mockUser = { id: "u1", email: "me@example.com", role: "AUTHORIZED_STAFF" };
    getDocumentMock.mockResolvedValue(doc({ owner_name: null }));
    wrap("/documents/d", <Route path="/documents/:id" element={<DocumentDetails />} />);
    expect(await screen.findByText("Unknown user")).toBeInTheDocument();
    expect(screen.getByText(OWNER_ID)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /view audit trail/i })).not.toBeInTheDocument();
  });
});

describe("Dashboard welcome (A)", () => {
  afterEach(() => {
    vi.clearAllMocks();
    mockUser = { id: "u1", email: "me@example.com", role: "AUDITOR" };
  });

  it("greets by name when there is one, otherwise by email", async () => {
    listDocumentsMock.mockResolvedValue({ items: [], page: 1, limit: 5, total: 0 });
    mockUser = { id: "u1", email: "me@example.com", role: "AUDITOR", name: "Ada Auditor" };
    const first = wrap("/", <Route path="/" element={<Dashboard />} />);
    expect(await screen.findByText(/, Ada Auditor/)).toBeInTheDocument();
    expect(screen.queryByText(/me@example\.com/)).not.toBeInTheDocument();
    first.unmount();

    mockUser = { id: "u1", email: "me@example.com", role: "AUDITOR" };
    wrap("/", <Route path="/" element={<Dashboard />} />);
    expect(await screen.findByText(/, me@example\.com/)).toBeInTheDocument();
  });
});
