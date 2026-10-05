import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ReportsSummary } from "../../../api/reports";
import ReportsPanel from "../ReportsPanel";

const getReportsSummaryMock = vi.fn();

vi.mock("../../../api/reports", async () => {
  const actual = await vi.importActual<typeof import("../../../api/reports")>("../../../api/reports");
  return { ...actual, getReportsSummary: (...a: unknown[]) => getReportsSummaryMock(...a) };
});

function summary(verifications: Partial<ReportsSummary["verifications_recent"]>): ReportsSummary {
  return {
    documents_by_status: [],
    documents_by_doc_type: [],
    anchoring: { pending: 0, confirmed: 3, failed: 0, success_rate: 1 },
    verifications_recent: {
      verified: 5,
      mismatch: 0,
      not_anchored: 1,
      window_days: 30,
      ...verifications,
    },
    geofence_denied_count: 0,
  };
}

function renderPanel() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ReportsPanel />
    </QueryClientProvider>,
  );
}

function valueOf(label: RegExp): string {
  return screen.getByText(label).parentElement!.querySelector("p:last-child")!.textContent!;
}

describe("ReportsPanel verification counts (D-049)", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows the three new counts", async () => {
    getReportsSummaryMock.mockResolvedValue(
      summary({ anchor_missing: 2, file_missing: 1, chain_unreachable: 4 }),
    );
    renderPanel();

    expect(await screen.findByText(/Anchor missing \(30d\)/)).toBeInTheDocument();
    expect(valueOf(/Anchor missing/)).toBe("2");
    expect(valueOf(/File missing/)).toBe("1");
    expect(valueOf(/Chain unreachable/)).toBe("4");
  });

  it("falls back to 0 when an older server omits them", async () => {
    getReportsSummaryMock.mockResolvedValue(summary({}));
    renderPanel();

    expect(await screen.findByText(/Chain unreachable \(30d\)/)).toBeInTheDocument();
    expect(valueOf(/Anchor missing/)).toBe("0");
    expect(valueOf(/File missing/)).toBe("0");
    expect(valueOf(/Chain unreachable/)).toBe("0");
  });
});
