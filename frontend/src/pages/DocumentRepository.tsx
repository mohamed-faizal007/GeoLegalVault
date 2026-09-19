import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { listDocuments } from "../api/documents";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import StatusBadge from "../components/StatusBadge";
import { formatDateTime } from "../lib/format";

const STATUS_OPTIONS = [
  "",
  "DRAFT",
  "SUBMITTED",
  "UNDER_REVIEW",
  "PENDING_APPROVAL",
  "CHANGES_REQUESTED",
  "APPROVED",
  "BLOCKCHAIN_ANCHORED",
  "ACTIVE",
  "AMENDMENT_REQUESTED",
  "SUPERSEDED",
  "ARCHIVED",
];

const LIMIT = 20;

export default function DocumentRepository() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [docType, setDocType] = useState("");
  const [page, setPage] = useState(1);

  const documentsQuery = useQuery({
    queryKey: ["documents", "list", { query, status, docType, page }],
    queryFn: () =>
      listDocuments({
        query: query || undefined,
        status: status || undefined,
        doc_type: docType || undefined,
        page,
        limit: LIMIT,
      }),
  });

  const totalPages = documentsQuery.data ? Math.max(1, Math.ceil(documentsQuery.data.total / LIMIT)) : 1;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Document Repository</h1>
      </div>

      <div className="flex flex-wrap gap-3 card-pad">
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(1);
          }}
          placeholder="Search title or tags…"
          className="input min-w-[200px] flex-1"
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          className="input w-auto"
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s ? s.replaceAll("_", " ") : "All statuses"}
            </option>
          ))}
        </select>
        <input
          value={docType}
          onChange={(e) => {
            setDocType(e.target.value);
            setPage(1);
          }}
          placeholder="Doc type…"
          className="input w-40"
        />
      </div>

      <div className="card overflow-hidden">
        {documentsQuery.isLoading && <Spinner label="Loading documents…" />}
        {documentsQuery.error && (
          <div className="p-4">
            <ErrorBanner error={documentsQuery.error} />
          </div>
        )}
        {documentsQuery.data && documentsQuery.data.items.length === 0 && (
          <div className="p-6">
            <EmptyState
              title="No documents match your filters"
              hint="Try clearing the search, status, or type filters."
            />
          </div>
        )}
        {documentsQuery.data && documentsQuery.data.items.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead className="table-head">
              <tr>
                <th className="px-4 py-2.5 font-medium">Title</th>
                <th className="px-4 py-2.5 font-medium">Type</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {documentsQuery.data.items.map((doc) => (
                <tr key={doc.id} className="table-row-hover">
                  <td className="px-4 py-3">
                    <Link to={`/documents/${doc.id}`} className="font-medium text-ink hover:text-brand-300 hover:underline">
                      {doc.title}
                    </Link>
                    {doc.integrity_flag === "TAMPERED" && (
                      <span className="ml-2 inline-flex items-center rounded-full bg-red-500/10 px-2 py-0.5 text-xs font-medium text-red-300 ring-1 ring-inset ring-red-400/30">
                        TAMPERED
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted">{doc.doc_type}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={doc.status} />
                  </td>
                  <td className="px-4 py-3 text-muted">{formatDateTime(doc.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {documentsQuery.data && documentsQuery.data.total > 0 && (
        <div className="flex items-center justify-between text-sm text-muted">
          <span>
            Page {page} of {totalPages} — {documentsQuery.data.total} total
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="btn-secondary btn-sm"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="btn-secondary btn-sm"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
