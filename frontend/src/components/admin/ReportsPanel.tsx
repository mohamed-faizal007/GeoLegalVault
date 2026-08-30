import { useQuery } from "@tanstack/react-query";

import { getReportsSummary, type DocTypeCount, type StatusCount } from "../../api/reports";
import ErrorBanner from "../ErrorBanner";
import Spinner from "../Spinner";

function StatCard({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string | number;
  tone?: "default" | "good" | "bad";
}) {
  const toneClass =
    tone === "good" ? "text-emerald-600" : tone === "bad" ? "text-red-600" : "text-slate-900";
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${toneClass}`}>{value}</p>
    </div>
  );
}

/** Simple horizontal bar chart — no charting library, just div widths. */
function BarChart({
  title,
  rows,
}: {
  title: string;
  rows: { label: string; count: number }[];
}) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-sm font-semibold text-slate-800">{title}</h2>
      {rows.length === 0 && <p className="text-sm text-slate-400">No data yet.</p>}
      <div className="space-y-2">
        {rows.map((row) => (
          <div key={row.label}>
            <div className="mb-0.5 flex justify-between text-xs text-slate-500">
              <span>{row.label.replaceAll("_", " ")}</span>
              <span>{row.count}</span>
            </div>
            <div className="h-2 rounded-full bg-slate-100">
              <div
                className="h-2 rounded-full bg-slate-700"
                style={{ width: `${(row.count / max) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ReportsPanel() {
  const summaryQuery = useQuery({
    queryKey: ["admin", "reports-summary"],
    queryFn: getReportsSummary,
  });

  if (summaryQuery.isLoading) return <Spinner label="Loading report data…" />;
  if (summaryQuery.error) return <ErrorBanner error={summaryQuery.error} />;
  if (!summaryQuery.data) return null;

  const { anchoring, verifications_recent, geofence_denied_count, documents_by_status, documents_by_doc_type } =
    summaryQuery.data;

  const statusRows: StatusCount[] = documents_by_status;
  const docTypeRows: DocTypeCount[] = documents_by_doc_type;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          label="Anchoring success rate"
          value={`${Math.round(anchoring.success_rate * 100)}%`}
          tone={anchoring.failed > 0 ? "bad" : "good"}
        />
        <StatCard label="Anchors confirmed" value={anchoring.confirmed} tone="good" />
        <StatCard label="Anchors failed" value={anchoring.failed} tone={anchoring.failed > 0 ? "bad" : "default"} />
        <StatCard label="Anchors pending" value={anchoring.pending} />
        <StatCard
          label={`Verified (${verifications_recent.window_days}d)`}
          value={verifications_recent.verified}
          tone="good"
        />
        <StatCard
          label={`Mismatches (${verifications_recent.window_days}d)`}
          value={verifications_recent.mismatch}
          tone={verifications_recent.mismatch > 0 ? "bad" : "default"}
        />
        <StatCard label="Not yet anchored" value={verifications_recent.not_anchored} />
        <StatCard
          label="Geofence denials (all-time)"
          value={geofence_denied_count}
          tone={geofence_denied_count > 0 ? "bad" : "default"}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <BarChart
          title="Documents by status"
          rows={statusRows.map((r) => ({ label: r.status, count: r.count }))}
        />
        <BarChart
          title="Documents by type"
          rows={docTypeRows.map((r) => ({ label: r.doc_type, count: r.count }))}
        />
      </div>
    </div>
  );
}
