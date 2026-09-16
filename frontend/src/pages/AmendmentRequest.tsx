import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { amendDocument, getDocument, uploadDocument, type UploadFields } from "../api/documents";
import type { GeoCoords } from "../api/http";
import ErrorBanner from "../components/ErrorBanner";
import FileDropzone from "../components/FileDropzone";
import LocationGate from "../components/LocationGate";
import Spinner from "../components/Spinner";

export default function AmendmentRequest() {
  const { id } = useParams<{ id: string }>();
  const documentId = id!;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [tags, setTags] = useState("");

  const docQuery = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => getDocument(documentId),
  });

  const requestMutation = useMutation({
    mutationFn: (coords: GeoCoords) => amendDocument(documentId, reason, coords),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["document", documentId] }),
  });

  const uploadMutation = useMutation({
    mutationFn: ({ coords }: { coords: GeoCoords }) => {
      if (!docQuery.data) throw new Error("Document not loaded");
      const fields: UploadFields = {
        title: docQuery.data.title,
        doc_type: docQuery.data.doc_type,
        classification: docQuery.data.classification,
        tags,
        amend_of: documentId,
      };
      return uploadDocument(file!, fields, coords);
    },
    onSuccess: () => navigate(`/documents/${documentId}`),
  });

  if (docQuery.isLoading) return <Spinner label="Loading document…" />;
  if (docQuery.error) return <ErrorBanner error={docQuery.error} />;
  if (!docQuery.data) return null;

  const readyForNewVersion = docQuery.data.status === "AMENDMENT_REQUESTED";

  function handleRequestSubmit(e: FormEvent, coords: GeoCoords) {
    e.preventDefault();
    requestMutation.mutate(coords);
  }

  function handleUploadSubmit(e: FormEvent, coords: GeoCoords) {
    e.preventDefault();
    if (!file) return;
    uploadMutation.mutate({ coords });
  }

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Amend: {docQuery.data.title}</h1>

      {!readyForNewVersion && (
        <LocationGate>
          {(coords) => (
            <form
              onSubmit={(e) => handleRequestSubmit(e, coords)}
              className="card space-y-4 p-6"
            >
              <div>
                <label className="field-label">
                  Reason for amendment
                </label>
                <textarea
                  required
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={3}
                  className="input mt-1"
                />
              </div>
              {requestMutation.error && <ErrorBanner error={requestMutation.error} />}
              <button type="submit" disabled={requestMutation.isPending} className="btn-primary w-full">
                {requestMutation.isPending ? "Submitting…" : "Request amendment"}
              </button>
            </form>
          )}
        </LocationGate>
      )}

      {readyForNewVersion && (
        <LocationGate>
          {(coords) => (
            <form
              onSubmit={(e) => handleUploadSubmit(e, coords)}
              className="card space-y-4 p-6"
            >
              <p className="text-sm text-slate-500">
                Amendment approved for a new version — upload the corrected file below to create
                the next version.
              </p>
              <div>
                <label className="field-label">
                  Tags (comma separated)
                </label>
                <input
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  className="input mt-1"
                />
              </div>
              <FileDropzone file={file} onChange={setFile} />
              {uploadMutation.error && <ErrorBanner error={uploadMutation.error} />}
              <button type="submit" disabled={!file || uploadMutation.isPending} className="btn-primary w-full">
                {uploadMutation.isPending ? "Uploading…" : "Upload new version"}
              </button>
            </form>
          )}
        </LocationGate>
      )}
    </div>
  );
}
