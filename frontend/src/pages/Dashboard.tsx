import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listDocuments } from "../api/documents";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import StatusBadge from "../components/StatusBadge";
import { useAuth } from "../context/useAuth";
import { useGeoLocation } from "../hooks/useGeoLocation";
import { formatDateTime } from "../lib/format";
import { hasPermission, PERMISSIONS, ROLE_LABELS, type Role } from "../lib/permissions";

const ROLE_QUEUE_STATUS: Partial<Record<Role, string>> = {
  REVIEWING_OFFICER: "SUBMITTED",
  LEGAL_OFFICER: "PENDING_APPROVAL",
};

function StatCard({ label, value, to }: { label: string; value: number | string; to?: string }) {
  const content = (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
  return to ? (
    <Link to={to} className="block transition hover:shadow-md">
      {content}
    </Link>
  ) : (
    content
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const role = user?.role as Role | undefined;
  const geo = useGeoLocation(true);

  const totalQuery = useQuery({
    queryKey: ["documents", "total"],
    queryFn: () => listDocuments({ limit: 1 }),
  });
  const myDraftsQuery = useQuery({
    queryKey: ["documents", "my-drafts", user?.id],
    queryFn: () => listDocuments({ owner: user!.id, status: "DRAFT", limit: 1 }),
    enabled: !!user,
  });
  const queueStatus = role ? ROLE_QUEUE_STATUS[role] : undefined;
  const queueQuery = useQuery({
    queryKey: ["documents", "queue", queueStatus],
    queryFn: () => listDocuments({ status: queueStatus, limit: 1 }),
    enabled: !!queueStatus,
  });
  const recentQuery = useQuery({
    queryKey: ["documents", "recent"],
    queryFn: () => listDocuments({ limit: 5 }),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">
          Welcome{user?.email ? `, ${user.email}` : ""}
        </h1>
        <p className="text-sm text-slate-500">
          {role ? ROLE_LABELS[role] : ""} — here's what's happening across the vault.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          label="Total documents"
          value={totalQuery.data?.total ?? (totalQuery.isLoading ? "…" : "—")}
          to="/documents"
        />
        {hasPermission(role, PERMISSIONS.DOCUMENT_UPLOAD) && (
          <StatCard
            label="My drafts"
            value={myDraftsQuery.data?.total ?? (myDraftsQuery.isLoading ? "…" : "—")}
            to="/documents"
          />
        )}
        {queueStatus && (
          <StatCard
            label={queueStatus === "SUBMITTED" ? "Awaiting my review" : "Awaiting my approval"}
            value={queueQuery.data?.total ?? (queueQuery.isLoading ? "…" : "—")}
            to="/documents"
          />
        )}
        <Link to="/geofence-status" className="block transition hover:shadow-md">
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Location status
            </p>
            <p className="mt-1 text-sm font-semibold text-slate-900">
              {geo.loading
                ? "Locating…"
                : geo.coords
                  ? `±${Math.round(geo.coords.accuracy)}m accuracy`
                  : "Unavailable"}
            </p>
          </div>
        </Link>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-800">Recent documents</h2>
          <Link to="/documents" className="text-xs font-medium text-slate-500 hover:underline">
            View all
          </Link>
        </div>
        {recentQuery.isLoading && <Spinner label="Loading recent documents…" />}
        {recentQuery.error && <div className="p-4"><ErrorBanner error={recentQuery.error} /></div>}
        {recentQuery.data && recentQuery.data.items.length === 0 && (
          <p className="px-4 py-6 text-sm text-slate-400">No documents yet.</p>
        )}
        {recentQuery.data && recentQuery.data.items.length > 0 && (
          <ul className="divide-y divide-slate-100">
            {recentQuery.data.items.map((doc) => (
              <li key={doc.id}>
                <Link
                  to={`/documents/${doc.id}`}
                  className="flex items-center justify-between px-4 py-3 hover:bg-slate-50"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-800">{doc.title}</p>
                    <p className="text-xs text-slate-400">
                      {doc.doc_type} — updated {formatDateTime(doc.updated_at)}
                    </p>
                  </div>
                  <StatusBadge status={doc.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
