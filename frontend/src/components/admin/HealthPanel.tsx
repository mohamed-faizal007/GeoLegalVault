import { useQuery } from "@tanstack/react-query";

import { fetchHealth } from "../../api/health";
import ErrorBanner from "../ErrorBanner";
import Spinner from "../Spinner";

function statusColor(value: string): string {
  if (value === "ok" || value === "reachable") return "text-emerald-300";
  if (value === "degraded") return "text-amber-300";
  return "text-red-300";
}

export default function HealthPanel() {
  const healthQuery = useQuery({
    queryKey: ["admin", "health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  });

  if (healthQuery.isLoading) return <Spinner label="Checking system health…" />;
  if (healthQuery.error) return <ErrorBanner error={healthQuery.error} />;
  if (!healthQuery.data) return null;

  const rows: [string, string][] = [
    ["Overall", healthQuery.data.status],
    ["MongoDB", healthQuery.data.mongo],
    ["Storage (R2/MinIO)", healthQuery.data.storage],
    ["Blockchain RPC", healthQuery.data.chain],
  ];

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      {rows.map(([label, value]) => (
        <div key={label} className="card-pad">
          <p className="text-xs uppercase tracking-wide text-faint">{label}</p>
          <p className={`mt-1.5 text-sm font-semibold ${statusColor(value)}`}>{value}</p>
        </div>
      ))}
    </div>
  );
}
