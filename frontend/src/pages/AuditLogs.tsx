import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { listAuditLogs } from "../api/audit";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import { formatDateTime, localDayEndISO, localDayStartISO } from "../lib/format";

const LIMIT = 25;
const FILTER_KEYS = [
  "action",
  "result",
  "target_type",
  "actor_id",
  "target_id",
  "date_from",
  "date_to",
] as const;
type FilterKey = (typeof FILTER_KEYS)[number];

export default function AuditLogs() {
  // Filters live in the URL so a filtered view can be bookmarked or shared.
  const [params, setParams] = useSearchParams();
  const f = (key: FilterKey) => params.get(key) ?? "";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const hasFilters = FILTER_KEYS.some((key) => f(key));

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
        actor_id: f("actor_id").trim() || undefined,
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
        <div className="flex flex-wrap gap-3">
          <input
            value={f("action")}
            onChange={(e) => setFilter("action", e.target.value)}
            placeholder="Action (e.g. LOGIN_SUCCESS)"
            aria-label="Action"
            className="input w-56"
          />
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
                  <td className="px-4 py-2.5 font-mono text-xs text-muted">
                    {entry.actor_id ? (
                      <button
                        type="button"
                        title="Filter by this actor"
                        onClick={() => setFilter("actor_id", entry.actor_id!)}
                        className="font-mono hover:text-brand-300 hover:underline"
                      >
                        {entry.actor_id}
                      </button>
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
                          className="hover:text-brand-300 hover:underline"
                        >
                          {entry.target_id}
                        </button>
                      </>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`font-medium ${
                        entry.result === "SUCCESS"
                          ? "text-emerald-300"
                          : entry.result === "DENIED" || entry.result === "MISMATCH" || entry.result === "FAILED"
                            ? "text-red-300"
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
