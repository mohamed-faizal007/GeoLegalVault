import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/http";
import Upload from "../Upload";

const uploadMock = vi.fn();
const COORDS = { lat: 11.67, lng: 78.15, accuracy: 10, timestamp: 1_700_000_000 };

vi.mock("../../api/documents", () => ({
  uploadDocument: (...a: unknown[]) => uploadMock(...a),
}));
vi.mock("../../components/LocationGate", () => ({
  default: ({ children }: { children: (c: typeof COORDS, r: () => void) => React.ReactNode }) =>
    children(COORDS, () => {}),
}));

function renderUpload() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Upload />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>, level?: string) {
  await user.type(screen.getByLabelText("Title"), "Vendor NDA");
  await user.type(screen.getByLabelText("Document type"), "CONTRACT");
  if (level) await user.selectOptions(screen.getByLabelText("Classification"), level);
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  await user.upload(input, new File(["hello"], "nda.pdf", { type: "application/pdf" }));
  await user.click(screen.getByRole("button", { name: "Upload" }));
}

describe("Upload classification", () => {
  afterEach(() => vi.clearAllMocks());

  it("offers the five levels in order and preselects none", () => {
    renderUpload();
    const select = screen.getByLabelText("Classification") as HTMLSelectElement;
    expect(select).toBeRequired();
    expect(select.value).toBe("");
    expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Choose a level",
      "Public",
      "Internal",
      "Confidential",
      "Restricted",
      "Top secret",
    ]);
  });

  it("sends the exact level value", async () => {
    uploadMock.mockResolvedValue({ document_id: "d-1" });
    const user = userEvent.setup();
    renderUpload();
    await fillAndSubmit(user, "TOP_SECRET");
    expect(uploadMock).toHaveBeenCalledWith(
      expect.any(File),
      expect.objectContaining({ classification: "TOP_SECRET" }),
      COORDS,
    );
  });

  it("does not submit without a level", async () => {
    const user = userEvent.setup();
    renderUpload();
    await fillAndSubmit(user);
    expect(uploadMock).not.toHaveBeenCalled();
  });

  it("explains in plain words when the server refuses a level above the clearance", async () => {
    uploadMock.mockRejectedValue(
      new ApiError(403, "CLASSIFICATION_NOT_ALLOWED", "classification above your clearance"),
    );
    const user = userEvent.setup();
    renderUpload();
    await fillAndSubmit(user, "TOP_SECRET");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /can't classify a document above your own clearance/i,
    );
  });
});
