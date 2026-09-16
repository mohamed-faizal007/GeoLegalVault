import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listAuditLogs } from "../api/audit";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import { formatDateTime } from "../lib/format";

const LIMIT = 25;

export default function AuditLogs() {
  const [action, setAction] = useState("");
  const [result, setResult] = useState("");
  const [targetType, setTargetType] = useState("");
  const [page, setPage] = useState(1);

  const auditQuery = useQuery({
    queryKey: ["audit", { action, result, targetType, page }],
    queryFn: () =>
      listAuditLogs({
        action: action || undefined,
        result: result || undefined,
        target_type: targetType || undefined,
        page,
        limit: LIMIT,
      }),
  });

  const totalPages = auditQuery.data ? Math.max(1, Math.ceil(auditQuery.data.total / LIMIT)) : 1;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Audit Logs</h1>

      <div className="flex flex-wrap gap-3 card-pad">
        <input
          value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setPage(1);
          }}
          placeholder="Action (e.g. LOGIN_SUCCESS)"
          className="input w-56"
        />
        <input
          value={result}
          onChange={(e) => {
            setResult(e.target.value);
            setPage(1);
          }}
          placeholder="Result (e.g. SUCCESS)"
          className="input w-48"
        />
        <input
          value={targetType}
          onChange={(e) => {
            setTargetType(e.target.value);
            setPage(1);
          }}
          placeholder="Target type (e.g. document)"
          className="input w-56"
        />
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
            <tbody className="divide-y divide-slate-100">
              {auditQuery.data.items.map((entry) => (
                <tr key={entry.id} className="table-row-hover">
                  <td className="whitespace-nowrap px-4 py-2.5 text-slate-500">
                    {formatDateTime(entry.created_at)}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-600">
                    {entry.actor_id ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 font-medium text-slate-800">{entry.action}</td>
                  <td className="px-4 py-2.5 text-slate-500">
                    {entry.target_type}
                    {entry.target_id ? ` / ${entry.target_id}` : ""}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`font-medium ${
                        entry.result === "SUCCESS"
                          ? "text-emerald-600"
                          : entry.result === "DENIED" || entry.result === "MISMATCH" || entry.result === "FAILED"
                            ? "text-red-600"
                            : "text-slate-500"
                      }`}
                    >
                      {entry.result}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-slate-400">{entry.ip ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {auditQuery.data && auditQuery.data.total > 0 && (
        <div className="flex items-center justify-between text-sm text-slate-500">
          <span>
            Page {page} of {totalPages} — {auditQuery.data.total} total
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
