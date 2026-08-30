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
        <h1 className="text-lg font-semibold text-slate-900">Document Repository</h1>
      </div>

      <div className="flex flex-wrap gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(1);
          }}
          placeholder="Search title or tags…"
          className="min-w-[200px] flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm"
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
          className="w-40 rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      </div>

      <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
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
            <thead className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">Title</th>
                <th className="px-4 py-2 font-medium">Type</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {documentsQuery.data.items.map((doc) => (
                <tr key={doc.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Link to={`/documents/${doc.id}`} className="font-medium text-slate-800 hover:underline">
                      {doc.title}
                    </Link>
                    {doc.integrity_flag === "TAMPERED" && (
                      <span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                        TAMPERED
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-500">{doc.doc_type}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={doc.status} />
                  </td>
                  <td className="px-4 py-3 text-slate-500">{formatDateTime(doc.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {documentsQuery.data && documentsQuery.data.total > 0 && (
        <div className="flex items-center justify-between text-sm text-slate-500">
          <span>
            Page {page} of {totalPages} — {documentsQuery.data.total} total
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="rounded-md border border-slate-300 px-3 py-1.5 disabled:opacity-40"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-md border border-slate-300 px-3 py-1.5 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
