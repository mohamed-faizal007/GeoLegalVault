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
        className={`cursor-pointer rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors ${
          dragging ? "border-slate-500 bg-slate-50" : "border-slate-300 hover:border-slate-400"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          onChange={(e) => onChange(e.target.files?.[0] ?? null)}
        />
        {file ? (
          <div>
            <p className="text-sm font-medium text-slate-700">{file.name}</p>
            <p className="mt-1 text-xs text-slate-400">
              {(file.size / 1024 / 1024).toFixed(2)} MB — click or drop to replace
            </p>
          </div>
        ) : (
          <div>
            <p className="text-sm font-medium text-slate-600">
              Drag & drop a file here, or click to choose one
            </p>
            <p className="mt-1 text-xs text-slate-400">
              Suggested: under {MAX_UPLOAD_MB_HINT}MB, types like {ACCEPTED_HINT}. The server is
              the source of truth for what's actually accepted.
            </p>
          </div>
        )}
      </div>
      {sizeHint && <p className="mt-1 text-xs text-amber-600">{sizeHint}</p>}
    </div>
  );
}
