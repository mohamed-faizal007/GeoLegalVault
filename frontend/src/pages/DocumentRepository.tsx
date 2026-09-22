import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { listDocuments } from "../api/documents";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import StatusBadge from "../components/StatusBadge";
import { useAuth } from "../context/useAuth";
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
  // Filters live in the URL so dashboard queue cards can deep-link here
  // (e.g. /documents?status=SUBMITTED) and Back restores the filter.
  const [params, setParams] = useSearchParams();
  const { user } = useAuth();
  const query = params.get("query") ?? "";
  const status = params.get("status") ?? "";
  const docType = params.get("doc_type") ?? "";
  const owner = params.get("owner") ?? "";
  const page = Math.max(1, Number(params.get("page")) || 1);
  // `owner=me` is a link convenience resolved to the signed-in user's id here.
  const ownerId = owner === "me" ? user?.id : owner || undefined;

  function setFilter(key: string, value: string) {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (value) next.set(key, value);
        else next.delete(key);
        if (key !== "page") next.delete("page");
        return next;
      },
      { replace: true },
    );
  }

  const documentsQuery = useQuery({
    queryKey: ["documents", "list", { query, status, docType, ownerId, page }],
    queryFn: () =>
      listDocuments({
        query: query || undefined,
        status: status || undefined,
        doc_type: docType || undefined,
        owner: ownerId,
        page,
        limit: LIMIT,
      }),
    enabled: owner !== "me" || !!user,
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
          onChange={(e) => setFilter("query", e.target.value)}
          placeholder="Search title or tags…"
          className="input min-w-[200px] flex-1"
        />
        <select
          value={status}
          onChange={(e) => setFilter("status", e.target.value)}
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
          onChange={(e) => setFilter("doc_type", e.target.value)}
          placeholder="Doc type…"
          className="input w-40"
        />
        {owner && (
          <button
            type="button"
            onClick={() => setFilter("owner", "")}
            className="btn-secondary btn-sm"
            aria-label="Clear owner filter"
          >
            {owner === "me" ? "My documents" : "One owner"} ✕
          </button>
        )}
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
              onClick={() => setFilter("page", String(Math.max(1, page - 1)))}
              className="btn-secondary btn-sm"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setFilter("page", String(page + 1))}
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
