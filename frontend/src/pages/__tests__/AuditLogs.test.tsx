import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { localDayEndISO, localDayStartISO } from "../../lib/format";
import AuditLogs from "../AuditLogs";

const listAuditLogsMock = vi.fn();

vi.mock("../../api/audit", async () => {
  const actual = await vi.importActual<typeof import("../../api/audit")>("../../api/audit");
  return { ...actual, listAuditLogs: (...a: unknown[]) => listAuditLogsMock(...a) };
});

const entry = {
  id: "a-1",
  actor_id: "actor-123",
  action: "UPLOAD",
  target_type: "document",
  target_id: "doc-456",
  result: "SUCCESS",
  ip: null,
  location: null,
  meta: {},
  created_at: "2026-03-10T12:00:00Z",
};

function renderAudit(path = "/audit") {
  listAuditLogsMock.mockResolvedValue({ items: [entry], page: 1, limit: 25, total: 1 });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/audit" element={<AuditLogs />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const lastCall = () => listAuditLogsMock.mock.calls.at(-1)![0];

describe("local day boundaries", () => {
  it("'to' covers the whole selected local day, 'from' starts it", () => {
    const start = new Date(localDayStartISO("2026-03-10")!);
    const end = new Date(localDayEndISO("2026-03-10")!);
    expect(start.getFullYear()).toBe(2026);
    expect([start.getMonth(), start.getDate(), start.getHours(), start.getMinutes()]).toEqual([
      2, 10, 0, 0,
    ]);
    // Last millisecond before the next local midnight (handles 23h/25h DST days too).
    const nextMidnight = new Date(2026, 2, 11);
    expect(end.getTime()).toBe(nextMidnight.getTime() - 1);
  });

  it("returns undefined for empty or malformed input", () => {
    expect(localDayStartISO("")).toBeUndefined();
    expect(localDayEndISO("10/03/2026")).toBeUndefined();
  });
});

describe("AuditLogs filters", () => {
  afterEach(() => vi.clearAllMocks());

  it("applies actor, target and date filters from the URL", async () => {
    renderAudit("/audit?actor_id=actor-123&target_id=doc-456&date_from=2026-03-01&date_to=2026-03-10");
    await screen.findByText("UPLOAD");
    expect(lastCall()).toEqual(
      expect.objectContaining({
        actor_id: "actor-123",
        target_id: "doc-456",
        date_from: localDayStartISO("2026-03-01"),
        date_to: localDayEndISO("2026-03-10"),
      }),
    );
    expect(screen.getByLabelText("Actor id")).toHaveValue("actor-123");
  });

  it("typing an actor id updates the query", async () => {
    renderAudit();
    await screen.findByText("UPLOAD");
    await userEvent.type(screen.getByLabelText("Actor id"), "abc");
    await vi.waitFor(() => expect(lastCall()).toEqual(expect.objectContaining({ actor_id: "abc" })));
  });

  it("clicking an actor id in the table filters by it, and Clear filters resets", async () => {
    renderAudit();
    await userEvent.click(await screen.findByRole("button", { name: "actor-123" }));
    await vi.waitFor(() =>
      expect(lastCall()).toEqual(expect.objectContaining({ actor_id: "actor-123" })),
    );

    await userEvent.click(screen.getByRole("button", { name: /clear filters/i }));
    await vi.waitFor(() => expect(lastCall().actor_id).toBeUndefined());
    expect(screen.queryByRole("button", { name: /clear filters/i })).not.toBeInTheDocument();
  });

  it("warns when the date range is inverted", async () => {
    renderAudit("/audit?date_from=2026-03-10&date_to=2026-03-01");
    expect(await screen.findByRole("alert")).toHaveTextContent(/after the To date/i);
  });
});
