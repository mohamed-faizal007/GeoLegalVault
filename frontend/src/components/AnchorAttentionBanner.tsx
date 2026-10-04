import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { fetchHealth } from "../api/health";
import { getAnchorAttention, retryAnchor, type AnchorAttentionItem } from "../api/blockchain";
import { useAuth } from "../context/useAuth";
import { getCurrentLocation } from "../hooks/useGeoLocation";
import { canRequestRetry, describeAnchorError, stateGuidance } from "../lib/anchorAttention";
import { formatDateTime } from "../lib/format";
import { hasPermission, PERMISSIONS } from "../lib/permissions";
import ErrorBanner from "./ErrorBanner";
import StatusBadge from "./StatusBadge";

const MIN_REASON = 10;

/**
 * Documents that are approved but whose blockchain anchor has not been recorded (REL-01).
 * Shown only to roles with `anchor:view`; renders nothing when everything is anchored.
 * The Retry button is Administrator-only and asks the server to re-queue the anchor: it never
 * signs anything and never names what to anchor. Every state is written out in words.
 */
export default function AnchorAttentionBanner() {
  const { user } = useAuth();
  const role = user?.role;
  const canView = hasPermission(role, PERMISSIONS.ANCHOR_VIEW);
  const canRetry = hasPermission(role, PERMISSIONS.ANCHOR_RETRY);
  const queryClient = useQueryClient();

  const [openId, setOpenId] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  const attention = useQuery({
    queryKey: ["anchors", "attention"],
    queryFn: getAnchorAttention,
    enabled: canView,
    refetchInterval: 30_000,
  });
  const items = attention.data?.items ?? [];

  // The retry only re-queues: if no worker is running, nothing will pick it up. Say so.
  const health = useQuery({
    queryKey: ["health", "anchor-banner"],
    queryFn: fetchHealth,
    enabled: canView && items.length > 0,
    refetchInterval: 60_000,
  });
  const workerStale = health.data?.anchor_worker === "stale";

  const retryMutation = useMutation({
    mutationFn: async (vars: { documentId: string; reason: string }) =>
      retryAnchor(vars.documentId, vars.reason, await getCurrentLocation()),
    onSuccess: (_data, vars) => {
      const title = items.find((item) => item.document_id === vars.documentId)?.title;
      setNotice(`Retry requested${title ? ` for “${title}”` : ""}. It is now back in the queue.`);
      setOpenId(null);
      setReason("");
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["anchors", "attention"] });
    },
    onError: setActionError,
  });

  if (!canView) return null;
  if (attention.error) return <ErrorBanner error={attention.error} />;
  if (items.length === 0 && !notice) return null;

  function openForm(documentId: string) {
    setOpenId(documentId);
    setReason("");
    setNotice(null);
    setActionError(null);
  }

  return (
    <section
      aria-labelledby="anchor-attention-title"
      className="card animate-fade-up overflow-hidden border-amber-400/30"
    >
      <div className="card-header px-5 py-4">
        <div className="flex items-start gap-3">
          <TriangleAlert size={20} aria-hidden="true" className="mt-0.5 shrink-0 text-amber-300" />
          <div>
            <h2 id="anchor-attention-title" className="text-base font-semibold tracking-tight text-ink">
              {items.length === 1
                ? "1 document is waiting for blockchain anchoring"
                : `${items.length} documents are waiting for blockchain anchoring`}
            </h2>
            <p className="mt-0.5 text-xs text-muted">
              These documents are approved, but the record of their hash on the chain has not been
              made yet. They stay in Approved until it is.
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-3 p-4">
        {workerStale && items.length > 0 && (
          <p role="status" className="rounded-lg border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
            The anchor worker does not appear to be running, so nothing will be retried until it is
            started.
          </p>
        )}
        {notice && (
          <p role="status" className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
            {notice}
          </p>
        )}

        <ul className="space-y-2">
          {items.map((item) => (
            <AttentionRow
              key={item.document_id}
              item={item}
              canRetry={canRetry}
              isOpen={openId === item.document_id}
              reason={reason}
              pending={retryMutation.isPending}
              onReasonChange={setReason}
              onOpen={() => openForm(item.document_id)}
              onCancel={() => setOpenId(null)}
              onSubmit={() =>
                retryMutation.mutate({ documentId: item.document_id, reason: reason.trim() })
              }
            />
          ))}
        </ul>

        {actionError !== null && <ErrorBanner error={actionError} />}
      </div>
    </section>
  );
}

function AttentionRow({
  item,
  canRetry,
  isOpen,
  reason,
  pending,
  onReasonChange,
  onOpen,
  onCancel,
  onSubmit,
}: {
  item: AnchorAttentionItem;
  canRetry: boolean;
  isOpen: boolean;
  reason: string;
  pending: boolean;
  onReasonChange: (value: string) => void;
  onOpen: () => void;
  onCancel: () => void;
  onSubmit: () => void;
}) {
  const mayRetry = canRetry && canRequestRetry(item.state, item.can_retry);
  const error = describeAnchorError(item.last_error);
  return (
    <li className="rounded-lg border border-white/10 bg-raised/40 p-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Link
          to={`/documents/${item.document_id}`}
          className="text-sm font-semibold text-ink hover:text-brand-200"
        >
          {item.title}
        </Link>
        <span className="text-xs text-muted">version {item.version_no}</span>
        <StatusBadge status={item.state} />
      </div>

      <p className="mt-2 text-sm text-ink/90">{stateGuidance(item.state, mayRetry)}</p>
      <p className="mt-1 text-xs text-muted">
        {error.label}
        {error.code && <span className="text-faint"> (code {error.code})</span>}
      </p>
      <p className="mt-1 text-xs text-muted">
        Stuck since {formatDateTime(item.stuck_since)} · {item.attempts}{" "}
        {item.attempts === 1 ? "automatic attempt" : "automatic attempts"} so far
        {item.next_attempt_at && item.state === "RETRYING"
          ? ` · next try ${formatDateTime(item.next_attempt_at)}`
          : ""}
      </p>

      {mayRetry && !isOpen && (
        <div className="mt-3">
          <button type="button" className="btn-secondary btn-sm" onClick={onOpen}>
            Retry anchoring
          </button>
        </div>
      )}

      {mayRetry && isOpen && (
        <div className="mt-3">
          <label className="field-label" htmlFor={`retry-reason-${item.document_id}`}>
            Reason for the retry
          </label>
          <p className="mt-1 text-xs text-muted">
            This only puts the anchor back in the queue; the background worker does the sending. Your
            reason is written to the audit log, so please don&apos;t include personal data.
          </p>
          <textarea
            id={`retry-reason-${item.document_id}`}
            value={reason}
            onChange={(e) => onReasonChange(e.target.value)}
            placeholder="Reason (required, at least 10 characters) — e.g. wallet funded again"
            className="input mt-2"
            rows={2}
            maxLength={1000}
          />
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              className="btn-primary btn-sm"
              disabled={pending || reason.trim().length < MIN_REASON}
              onClick={onSubmit}
            >
              {pending ? "Sending request…" : "Send retry request"}
            </button>
            <button type="button" className="btn-secondary btn-sm" disabled={pending} onClick={onCancel}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </li>
  );
}
