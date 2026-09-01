import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import FileDropzone from "../FileDropzone";

function makeFile(name: string, sizeBytes: number, type = "application/pdf"): File {
  const file = new File(["x"], name, { type });
  Object.defineProperty(file, "size", { value: sizeBytes });
  return file;
}

describe("FileDropzone", () => {
  it("shows the drop prompt and size/type hint when no file is chosen", () => {
    render(<FileDropzone file={null} onChange={vi.fn()} />);

    expect(screen.getByText(/drag & drop a file here/i)).toBeInTheDocument();
    expect(screen.getByText(/under 10MB/i)).toBeInTheDocument();
  });

  it("shows the chosen file's name and size once selected", () => {
    const file = makeFile("contract.pdf", 2 * 1024 * 1024);
    render(<FileDropzone file={file} onChange={vi.fn()} />);

    expect(screen.getByText("contract.pdf")).toBeInTheDocument();
    expect(screen.getByText(/2\.00 MB/)).toBeInTheDocument();
  });

  it("warns — but does not block — when a file exceeds the 10MB client-side hint", () => {
    // The server is the real source of truth (Guardrail: client hints only),
    // so this is a warning, not a disabled state.
    const oversized = makeFile("big.pdf", 11 * 1024 * 1024);
    render(<FileDropzone file={oversized} onChange={vi.fn()} />);

    expect(screen.getByText(/larger than the 10MB hint/i)).toBeInTheDocument();
  });

  it("does not show the oversize warning for a file under the hint", () => {
    const small = makeFile("small.pdf", 1024);
    render(<FileDropzone file={small} onChange={vi.fn()} />);

    expect(screen.queryByText(/larger than the 10MB hint/i)).not.toBeInTheDocument();
  });

  it("calls onChange with the file selected via the hidden input", async () => {
    const onChange = vi.fn();
    render(<FileDropzone file={null} onChange={onChange} />);

    const file = makeFile("contract.pdf", 1024);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, file);

    expect(onChange).toHaveBeenCalledWith(file);
  });
});
