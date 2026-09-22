import { useQuery } from "@tanstack/react-query";
import {
  ChevronRight,
  ClipboardCheck,
  FileText,
  Files,
  MapPin,
  PencilLine,
  type LucideIcon,
} from "lucide-react";
import { Link } from "react-router-dom";

import { listDocuments } from "../api/documents";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import StatusBadge from "../components/StatusBadge";
import { useAuth } from "../context/useAuth";
import { useGeoLocation } from "../hooks/useGeoLocation";
import { formatDateTime } from "../lib/format";
import { hasPermission, PERMISSIONS, ROLE_LABELS, type Role } from "../lib/permissions";
import { statusTone, TONE_BAR } from "../lib/status";

const ROLE_QUEUE_STATUS: Partial<Record<Role, string>> = {
  REVIEWING_OFFICER: "SUBMITTED",
  LEGAL_OFFICER: "PENDING_APPROVAL",
};

const CARD_BASE = "card card-hover group relative block overflow-hidden p-5 hover:-translate-y-0.5";

function IconTile({ icon: Icon }: { icon: LucideIcon }) {
  return (
    <span
      aria-hidden="true"
      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-500/15 text-brand-300 ring-1 ring-inset ring-brand-400/30 transition-shadow duration-200 group-hover:shadow-glow"
    >
      <Icon size={20} strokeWidth={1.75} />
    </span>
  );
}

function HoverChevron() {
  return (
    <ChevronRight
      size={14}
      aria-hidden="true"
      className="-translate-x-1 opacity-0 transition duration-200 group-hover:translate-x-0 group-hover:opacity-100"
    />
  );
}

/** While loading the number is a skeleton; on error it stays "—" as before. */
function StatCard({
  label,
  value,
  loading,
  hint,
  icon,
  to,
}: {
  label: string;
  value: number | string;
  loading: boolean;
  hint: string;
  icon: LucideIcon;
  to: string;
}) {
  return (
    <Link to={to} className={CARD_BASE}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-faint">{label}</p>
        <IconTile icon={icon} />
      </div>
      {loading ? (
        <div className="skeleton mt-3 h-9 w-16" role="status">
          <span className="sr-only">Loading</span>
        </div>
      ) : (
        <p className="mt-3 text-4xl font-bold tabular-nums tracking-tight text-ink">{value}</p>
      )}
      <p className="mt-2 flex items-center gap-1 text-xs text-muted">
        {hint}
        <HoverChevron />
      </p>
    </Link>
  );
}

/** Live location reading: pulsing dot while locating, steady dot once resolved.
 * The text always states the state, so colour is never the only signal. */
function LocationCard({ loading, accuracy }: { loading: boolean; accuracy: number | null }) {
  const state = loading ? "locating" : accuracy !== null ? "ready" : "unavailable";
  const dot =
    state === "ready" ? "bg-emerald-400" : state === "locating" ? "bg-brand-400" : "bg-amber-400";
  return (
    <Link to="/geofence-status" className={CARD_BASE}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-faint">Location status</p>
        <IconTile icon={MapPin} />
      </div>
      <p className="mt-3 flex items-center gap-2.5 text-ink">
        <span aria-hidden="true" className="relative flex h-2.5 w-2.5 shrink-0">
          {state === "locating" && (
            <span
              className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${dot}`}
            />
          )}
          <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${dot}`} />
        </span>
        <span
          role={state === "locating" ? "status" : undefined}
          className={
            state === "ready"
              ? "text-4xl font-bold tabular-nums tracking-tight"
              : "text-xl font-semibold tracking-tight"
          }
        >
          {state === "locating"
            ? "Locating…"
            : accuracy !== null
              ? `±${Math.round(accuracy)}m`
              : "Unavailable"}
        </span>
      </p>
      <p className="mt-2 flex items-center gap-1 text-xs text-muted">
        {state === "ready" ? "accuracy · live browser reading" : "Live browser reading"}
        <HoverChevron />
      </p>
    </Link>
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

  const total = (q: { data?: { total: number } }) => q.data?.total ?? "—";

  return (
    <div className="space-y-10">
      <header className="animate-fade-up">
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          <span className="text-gradient">Welcome</span>
          <span className="text-ink">{user?.email ? `, ${user.email}` : ""}</span>
        </h1>
        <p className="mt-2 text-base text-muted">
          {role ? ROLE_LABELS[role] : ""} — here's what's happening across the vault.
        </p>
      </header>

      <section aria-label="Key figures" className="anim-delay-1 animate-fade-up">
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Total documents"
            value={total(totalQuery)}
            loading={totalQuery.isLoading}
            hint="Everything you can access"
            icon={Files}
            to="/documents"
          />
          {hasPermission(role, PERMISSIONS.DOCUMENT_UPLOAD) && (
            <StatCard
              label="My drafts"
              value={total(myDraftsQuery)}
              loading={myDraftsQuery.isLoading}
              hint="Drafts you own"
              icon={PencilLine}
              to="/documents?status=DRAFT&owner=me"
            />
          )}
          {queueStatus && (
            <StatCard
              label={queueStatus === "SUBMITTED" ? "Awaiting my review" : "Awaiting my approval"}
              value={total(queueQuery)}
              loading={queueQuery.isLoading}
              hint={
                queueStatus === "SUBMITTED" ? "Submitted, ready to review" : "Reviewed, ready to approve"
              }
              icon={ClipboardCheck}
              to={`/documents?status=${queueStatus}`}
            />
          )}
          <LocationCard loading={geo.loading} accuracy={geo.coords ? geo.coords.accuracy : null} />
        </div>
      </section>

      <section className="anim-delay-2 animate-fade-up">
        <div className="card overflow-hidden">
          <div className="card-header px-5 py-4">
            <div>
              <h2 className="text-base font-semibold tracking-tight text-ink">Recent documents</h2>
              <p className="mt-0.5 text-xs text-muted">Latest activity across the vault</p>
            </div>
            <Link
              to="/documents"
              className="inline-flex items-center gap-1 rounded-md text-sm font-medium text-brand-300 transition-colors duration-150 hover:text-brand-200"
            >
              View all
              <ChevronRight size={16} aria-hidden="true" />
            </Link>
          </div>

          <div className="p-4">
            {recentQuery.isLoading && (
              <div role="status" className="space-y-2">
                <span className="sr-only">Loading recent documents…</span>
                {[0, 1, 2].map((i) => (
                  <div key={i} className="skeleton h-[4.5rem] w-full rounded-lg" />
                ))}
              </div>
            )}
            {recentQuery.error && <ErrorBanner error={recentQuery.error} />}
            {recentQuery.data && recentQuery.data.items.length === 0 && (
              <EmptyState title="No documents yet." />
            )}
            {recentQuery.data && recentQuery.data.items.length > 0 && (
              <ul className="space-y-2">
                {recentQuery.data.items.map((doc) => (
                  <li key={doc.id}>
                    <Link
                      to={`/documents/${doc.id}`}
                      className="card-hover group relative flex items-center gap-4 overflow-hidden rounded-lg border border-white/10 bg-raised/40 py-3 pl-5 pr-4 transition duration-200 hover:bg-raised/80"
                    >
                      {/* Left-edge status accent: a scanning aid; the badge text is the source of truth */}
                      <span
                        aria-hidden="true"
                        className={`absolute inset-y-0 left-0 w-1 ${TONE_BAR[statusTone(doc.status)]}`}
                      />
                      <span
                        aria-hidden="true"
                        className="hidden h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/5 text-muted ring-1 ring-inset ring-white/10 transition-colors duration-200 group-hover:text-brand-300 sm:flex"
                      >
                        <FileText size={20} strokeWidth={1.75} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-ink">{doc.title}</p>
                        <p className="mt-0.5 truncate text-xs text-muted">
                          {doc.doc_type} — updated {formatDateTime(doc.updated_at)}
                        </p>
                      </div>
                      <StatusBadge status={doc.status} />
                      <ChevronRight
                        size={18}
                        aria-hidden="true"
                        className="hidden shrink-0 -translate-x-1 text-faint opacity-0 transition duration-200 group-hover:translate-x-0 group-hover:text-brand-300 group-hover:opacity-100 sm:block"
                      />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
