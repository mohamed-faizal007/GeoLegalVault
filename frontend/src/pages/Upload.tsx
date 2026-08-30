import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { uploadDocument, type UploadFields } from "../api/documents";
import type { GeoCoords } from "../api/http";
import ErrorBanner from "../components/ErrorBanner";
import FileDropzone from "../components/FileDropzone";
import LocationGate from "../components/LocationGate";

export default function Upload() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [docType, setDocType] = useState("");
  const [classification, setClassification] = useState("");
  const [tags, setTags] = useState("");

  const mutation = useMutation({
    mutationFn: ({ coords }: { coords: GeoCoords }) => {
      const fields: UploadFields = { title, doc_type: docType, classification, tags };
      return uploadDocument(file!, fields, coords);
    },
    onSuccess: (result) => navigate(`/documents/${result.document_id}`),
  });

  function handleSubmit(e: FormEvent, coords: GeoCoords) {
    e.preventDefault();
    if (!file) return;
    mutation.mutate({ coords });
  }

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-lg font-semibold text-slate-900">Upload a Document</h1>

      <LocationGate>
        {(coords) => (
          <form
            onSubmit={(e) => handleSubmit(e, coords)}
            className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
          >
            <div>
              <label className="block text-sm font-medium text-slate-700">Title</label>
              <input
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700">Document type</label>
                <input
                  required
                  value={docType}
                  onChange={(e) => setDocType(e.target.value)}
                  placeholder="e.g. CONTRACT"
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700">Classification</label>
                <input
                  required
                  value={classification}
                  onChange={(e) => setClassification(e.target.value)}
                  placeholder="e.g. RESTRICTED"
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Tags (comma separated)</label>
              <input
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">File</label>
              <div className="mt-1">
                <FileDropzone file={file} onChange={setFile} />
              </div>
            </div>

            {mutation.error && <ErrorBanner error={mutation.error} />}

            <button
              type="submit"
              disabled={!file || mutation.isPending}
              className="w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {mutation.isPending ? "Uploading…" : "Upload"}
            </button>
          </form>
        )}
      </LocationGate>
    </div>
  );
}
