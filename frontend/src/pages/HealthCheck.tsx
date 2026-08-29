import { useQuery } from "@tanstack/react-query";

import { fetchHealth } from "../api/health";

export default function HealthCheck() {
  const { data, error, isLoading } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
  });

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="max-w-lg w-full bg-white rounded-lg shadow p-6">
        <h1 className="text-xl font-semibold text-slate-900 mb-1">GeoLegalVault</h1>
        <p className="text-sm text-slate-500 mb-4">Backend health check</p>

        {isLoading && <p className="text-slate-500">Checking backend...</p>}

        {error instanceof Error && (
          <p className="text-red-600">Could not reach backend: {error.message}</p>
        )}

        {data && (
          <pre className="bg-slate-100 rounded p-4 text-sm overflow-auto">
            {JSON.stringify(data, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
