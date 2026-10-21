import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { listAuditActions, listAuditLogs } from "../api/audit";
import { getDocument, listDocuments } from "../api/documents";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import { formatDateTime, localDayEndISO, localDayStartISO } from "../lib/format";

const LIMIT = 25;
const FILTER_KEYS = [
  "action",
  "result",
  "target_type",
  "actor",
  "actor_id",
  "document_id",
  "target_id",
  "date_from",
  "date_to",
] as const;
type FilterKey = (typeof FILTER_KEYS)[number];

function useDebounced(value: string, ms = 300): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

/** Id as secondary text: small, monospace, and never the only thing shown when a name exists. */
function IdText({ id }: { id: string }) {
  return <span className="block break-all font-mono text-[11px] text-faint">{id}</span>;
}

export default function AuditLogs() {
  // Filters live in the URL so a filtered view can be bookmarked or shared.
  const [params, setParams] = useSearchParams();
  const f = (key: FilterKey) => params.get(key) ?? "";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const hasFilters = FILTER_KEYS.some((key) => f(key));

  // Newest first is the server's order. Page changes come from this page's own buttons, so bring
  // the list back into view (the route change itself is handled by the layout).
  useEffect(() => {
    document.querySelector("main")?.scrollTo?.({ top: 0 });
  }, [page]);

  // Filter choices. The action list is whatever the log really contains.
  const actionsQuery = useQuery({
    queryKey: ["audit", "actions"],
    queryFn: listAuditActions,
    staleTime: 60_000,
  });
  const actionOptions = actionsQuery.data?.actions ?? [];
  // A document is found by title through the ordinary, clearance-filtered search, so this box can
  // never offer a document the viewer may not open.
  const [docSearch, setDocSearch] = useState("");
  const docTerm = useDebounced(docSearch.trim());
  const docResults = useQuery({
    queryKey: ["audit", "document-search", docTerm],
    queryFn: () => listDocuments({ query: docTerm, limit: 6 }),
    enabled: docTerm.length >= 2,
  });
  const selectedDocument = useQuery({
    queryKey: ["document", f("document_id")],
    queryFn: () => getDocument(f("document_id")),
    enabled: !!f("document_id"),
    retry: false,
  });

  function setFilter(key: FilterKey | "page", value: string) {
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

  const auditQuery = useQuery({
    queryKey: ["audit", Object.fromEntries(FILTER_KEYS.map((k) => [k, f(k)])), page],
    queryFn: () =>
      listAuditLogs({
        action: f("action") || undefined,
        result: f("result") || undefined,
        target_type: f("target_type") || undefined,
        actor: f("actor").trim().length >= 2 ? f("actor").trim() : undefined,
        actor_id: f("actor_id").trim() || undefined,
        document_id: f("document_id") || undefined,
        target_id: f("target_id").trim() || undefined,
        // Inclusive, local-day boundaries — see DECISIONS.md D-011.
        date_from: localDayStartISO(f("date_from")),
        date_to: localDayEndISO(f("date_to")),
        page,
        limit: LIMIT,
      }),
  });

  const totalPages = auditQuery.data ? Math.max(1, Math.ceil(auditQuery.data.total / LIMIT)) : 1;
  const rangeInverted = !!f("date_from") && !!f("date_to") && f("date_from") > f("date_to");

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight text-ink">Audit Logs</h1>

      <div className="space-y-3 card-pad">
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-faint">
            Action
            <select
              value={f("action")}
              onChange={(e) => setFilter("action", e.target.value)}
              className="input mt-1 block w-56"
            >
              <option value="">All actions</option>
              {/* Keep a value from the URL selectable even before the list has loaded. */}
              {f("action") && !actionOptions.includes(f("action")) && (
                <option value={f("action")}>{f("action")}</option>
              )}
              {actionOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-faint">
            Actor (name or email)
            <input
              value={f("actor")}
              onChange={(e) => setFilter("actor", e.target.value)}
              placeholder="e.g. Olivia"
              className="input mt-1 block w-56"
            />
          </label>
          <div className="relative text-xs text-faint">
            <label htmlFor="audit-doc-search">Document (find by title)</label>
            <input
              id="audit-doc-search"
              value={docSearch}
              onChange={(e) => setDocSearch(e.target.value)}
              placeholder="Type 2+ letters of a title"
              autoComplete="off"
              className="input mt-1 block w-64"
            />
            {docTerm.length >= 2 && docResults.data && docSearch.trim() === docTerm && (
              <ul
                aria-label="Matching documents"
                className="absolute z-20 mt-1 max-h-56 w-72 overflow-auto rounded-lg border border-white/10 bg-raised p-1 shadow-card-hover"
              >
                {docResults.data.items.length === 0 && (
                  <li className="px-3 py-2 text-xs text-muted">No documents match.</li>
                )}
                {docResults.data.items.map((d) => (
                  <li key={d.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setFilter("document_id", d.id);
                        setDocSearch("");
                      }}
                      className="w-full rounded-md px-3 py-1.5 text-left text-sm text-ink/90 hover:bg-white/10"
                    >
                      {d.title}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <input
            value={f("result")}
            onChange={(e) => setFilter("result", e.target.value)}
            placeholder="Result (e.g. SUCCESS)"
            aria-label="Result"
            className="input w-48"
          />
          <input
            value={f("target_type")}
            onChange={(e) => setFilter("target_type", e.target.value)}
            placeholder="Target type (e.g. document)"
            aria-label="Target type"
            className="input w-56"
          />
        </div>
        {f("document_id") && (
          <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
            Showing the history of document
            <strong className="text-ink">
              {selectedDocument.data?.title ?? `…${f("document_id").slice(-8)}`}
            </strong>
            and its versions
            <button
              type="button"
              onClick={() => setFilter("document_id", "")}
              className="btn-secondary btn-sm"
              aria-label="Remove document filter"
            >
              ✕
            </button>
          </p>
        )}
        <div className="flex flex-wrap items-end gap-3">
          <input
            value={f("actor_id")}
            onChange={(e) => setFilter("actor_id", e.target.value)}
            placeholder="Actor id"
            aria-label="Actor id"
            className="input w-56 font-mono text-xs"
          />
          <input
            value={f("target_id")}
            onChange={(e) => setFilter("target_id", e.target.value)}
            placeholder="Target id"
            aria-label="Target id"
            className="input w-56 font-mono text-xs"
          />
          <label className="text-xs text-faint">
            From
            <input
              type="date"
              value={f("date_from")}
              max={f("date_to") || undefined}
              onChange={(e) => setFilter("date_from", e.target.value)}
              className="input mt-1 block w-40"
            />
          </label>
          <label className="text-xs text-faint">
            To
            <input
              type="date"
              value={f("date_to")}
              min={f("date_from") || undefined}
              onChange={(e) => setFilter("date_to", e.target.value)}
              className="input mt-1 block w-40"
            />
          </label>
          {hasFilters && (
            <button
              type="button"
              onClick={() => setParams({}, { replace: true })}
              className="btn-secondary btn-sm"
            >
              Clear filters
            </button>
          )}
        </div>
        {rangeInverted && (
          <p role="alert" className="text-xs text-amber-300">
            The From date is after the To date, so no records can match this range.
          </p>
        )}
      </div>

      <div className="card overflow-x-auto">
        {auditQuery.isLoading && <Spinner label="Loading audit log…" />}
        {auditQuery.error && (
          <div className="p-4">
            <ErrorBanner error={auditQuery.error} />
          </div>
        )}
        {auditQuery.data && auditQuery.data.items.length === 0 && (
          <div className="p-6">
            <EmptyState title="No matching audit records" />
          </div>
        )}
        {auditQuery.data && auditQuery.data.items.length > 0 && (
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="table-head">
              <tr>
                <th className="px-4 py-2.5 font-medium">When</th>
                <th className="px-4 py-2.5 font-medium">Actor</th>
                <th className="px-4 py-2.5 font-medium">Action</th>
                <th className="px-4 py-2.5 font-medium">Target</th>
                <th className="px-4 py-2.5 font-medium">Result</th>
                <th className="px-4 py-2.5 font-medium">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {auditQuery.data.items.map((entry) => (
                <tr key={entry.id} className="table-row-hover">
                  <td className="whitespace-nowrap px-4 py-2.5 text-muted">
                    {formatDateTime(entry.created_at)}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-muted">
                    {entry.actor_id ? (
                      <>
                        <button
                          type="button"
                          title={
                            entry.actor_email
                              ? `Filter by this actor (${entry.actor_email})`
                              : "Filter by this actor"
                          }
                          onClick={() => setFilter("actor_id", entry.actor_id!)}
                          className={`text-left hover:text-brand-300 hover:underline ${
                            entry.actor_label ? "text-sm text-ink/90" : "font-mono"
                          }`}
                        >
                          {entry.actor_label ?? entry.actor_id}
                        </button>
                        {entry.actor_label === null && (
                          <span className="block text-[11px] italic text-faint">Unknown user</span>
                        )}
                        {entry.actor_label && entry.actor_label !== entry.actor_id && (
                          <IdText id={entry.actor_id} />
                        )}
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-4 py-2.5 font-medium text-ink">{entry.action}</td>
                  <td className="px-4 py-2.5 text-muted">
                    {entry.target_type}
                    {entry.target_id && (
                      <>
                        {" / "}
                        <button
                          type="button"
                          title="Filter by this target"
                          onClick={() => setFilter("target_id", entry.target_id!)}
                          className="text-left hover:text-brand-300 hover:underline"
                        >
                          {entry.target_label ?? entry.target_id}
                        </button>
                        {entry.target_label && <IdText id={entry.target_id} />}
                      </>
                    )}
                    {entry.redacted && (
                      <span
                        title="Details withheld: this record concerns a document above your clearance."
                        className="ml-2 inline-flex items-center rounded-full bg-white/5 px-2 py-0.5 text-xs font-medium text-faint ring-1 ring-inset ring-white/10"
                      >
                        details hidden
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`font-medium ${
                        entry.result === "SUCCESS"
                          ? "text-emerald-300"
                          : ["DENIED", "MISMATCH", "FAILED", "ANCHOR_MISSING", "FILE_MISSING"].includes(entry.result)
                            ? "text-red-300"
                            : ["CHAIN_UNREACHABLE", "STORAGE_UNAVAILABLE"].includes(entry.result)
                              ? "text-amber-300"
                              : "text-muted"
                      }`}
                    >
                      {entry.result}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-faint">{entry.ip ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {auditQuery.data && auditQuery.data.total > 0 && (
        <div className="flex items-center justify-between text-sm text-muted">
          <span>
            Page {page} of {totalPages} — {auditQuery.data.total} total
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
