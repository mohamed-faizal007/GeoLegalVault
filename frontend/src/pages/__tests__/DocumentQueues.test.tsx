import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import Dashboard from "../Dashboard";
import DocumentRepository from "../DocumentRepository";

const listDocumentsMock = vi.fn();
let mockRole = "REVIEWING_OFFICER";

vi.mock("../../api/documents", async () => {
  const actual = await vi.importActual<typeof import("../../api/documents")>("../../api/documents");
  return { ...actual, listDocuments: (...a: unknown[]) => listDocumentsMock(...a) };
});
vi.mock("../../context/useAuth", () => ({
  useAuth: () => ({
    user: { id: "u-me", email: "me@example.com", role: mockRole },
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));
vi.mock("../../hooks/useGeoLocation", () => ({
  useGeoLocation: () => ({ coords: null, error: null, loading: false, refresh: vi.fn() }),
}));

function renderAt(path: string, element: React.ReactNode, routePath: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={routePath} element={element} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const emptyList = { items: [], page: 1, limit: 20, total: 0 };

describe("queue deep links", () => {
  afterEach(() => {
    vi.clearAllMocks();
    mockRole = "REVIEWING_OFFICER";
  });

  it("repository applies status from the URL to the list call", async () => {
    listDocumentsMock.mockResolvedValue(emptyList);
    renderAt("/documents?status=SUBMITTED", <DocumentRepository />, "/documents");
    await screen.findByText(/no documents match/i);
    expect(listDocumentsMock).toHaveBeenCalledWith(
      expect.objectContaining({ status: "SUBMITTED", owner: undefined, page: 1 }),
    );
    expect(screen.getByRole("combobox")).toHaveValue("SUBMITTED");
  });

  it("repository resolves owner=me to the signed-in user's id and can clear it", async () => {
    listDocumentsMock.mockResolvedValue(emptyList);
    renderAt("/documents?status=DRAFT&owner=me", <DocumentRepository />, "/documents");
    await screen.findByText(/no documents match/i);
    expect(listDocumentsMock).toHaveBeenCalledWith(
      expect.objectContaining({ status: "DRAFT", owner: "u-me" }),
    );

    await userEvent.click(screen.getByRole("button", { name: /clear owner filter/i }));
    await vi.waitFor(() =>
      expect(listDocumentsMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: "DRAFT", owner: undefined }),
      ),
    );
  });

  it("changing the status filter updates the query", async () => {
    listDocumentsMock.mockResolvedValue(emptyList);
    renderAt("/documents", <DocumentRepository />, "/documents");
    await screen.findByText(/no documents match/i);
    await userEvent.selectOptions(screen.getByRole("combobox"), "PENDING_APPROVAL");
    await vi.waitFor(() =>
      expect(listDocumentsMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: "PENDING_APPROVAL" }),
      ),
    );
  });

  it("reviewer's dashboard queue card links to the SUBMITTED list", async () => {
    listDocumentsMock.mockResolvedValue(emptyList);
    renderAt("/", <Dashboard />, "/");
    const card = await screen.findByRole("link", { name: /awaiting my review/i });
    expect(card).toHaveAttribute("href", "/documents?status=SUBMITTED");
  });

  it("legal officer's cards link to approval queue and own drafts", async () => {
    mockRole = "LEGAL_OFFICER";
    listDocumentsMock.mockResolvedValue(emptyList);
    renderAt("/", <Dashboard />, "/");
    expect(await screen.findByRole("link", { name: /awaiting my approval/i })).toHaveAttribute(
      "href",
      "/documents?status=PENDING_APPROVAL",
    );
    expect(screen.getByRole("link", { name: /my drafts/i })).toHaveAttribute(
      "href",
      "/documents?status=DRAFT&owner=me",
    );
  });
});
