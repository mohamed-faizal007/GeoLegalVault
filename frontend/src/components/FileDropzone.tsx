import { useRef, useState } from "react";

const MAX_UPLOAD_MB_HINT = 10; // client-side hint only; the server enforces the real limit
const ACCEPTED_HINT = ".pdf, .docx, .txt, .png, .jpg";

export default function FileDropzone({
  file,
  onChange,
}: {
  file: File | null;
  onChange: (file: File | null) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const sizeHint =
    file && file.size > MAX_UPLOAD_MB_HINT * 1024 * 1024
      ? `This file is larger than the ${MAX_UPLOAD_MB_HINT}MB hint — the server will reject it if it exceeds the real limit.`
      : null;

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const dropped = e.dataTransfer.files?.[0];
          if (dropped) onChange(dropped);
        }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed px-6 py-10 text-center transition duration-200 ${
          dragging ? "border-brand-400 bg-brand-500/10 shadow-glow" : "border-white/20 hover:border-brand-400/60 hover:bg-white/5"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          onChange={(e) => onChange(e.target.files?.[0] ?? null)}
        />
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          className={`mx-auto h-8 w-8 ${dragging ? "text-brand-300" : "text-faint"}`}
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 16V4m0 0 4 4m-4-4-4 4M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
        </svg>
        {file ? (
          <div className="mt-3">
            <p className="text-sm font-medium text-ink">{file.name}</p>
            <p className="mt-1 text-xs text-muted">
              {(file.size / 1024 / 1024).toFixed(2)} MB — click or drop to replace
            </p>
          </div>
        ) : (
          <div className="mt-3">
            <p className="text-sm font-medium text-ink/90">
              Drag & drop a file here, or click to choose one
            </p>
            <p className="mt-1 text-xs text-muted">
              Suggested: under {MAX_UPLOAD_MB_HINT}MB, types like {ACCEPTED_HINT}. The server is
              the source of truth for what's actually accepted.
            </p>
          </div>
        )}
      </div>
      {sizeHint && <p className="mt-1 text-xs text-amber-300">{sizeHint}</p>}
    </div>
  );
}
