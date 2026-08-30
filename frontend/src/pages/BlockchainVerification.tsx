import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useParams } from "react-router-dom";

import { getAnchor } from "../api/blockchain";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import StatusBadge from "../components/StatusBadge";
import { ApiError } from "../api/http";
import { formatDateTime } from "../lib/format";

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-slate-100 py-2 last:border-0">
      <span className="text-xs uppercase tracking-wide text-slate-400">{label}</span>
      <span className="break-all text-sm text-slate-700">{value}</span>
    </div>
  );
}

export default function BlockchainVerification() {
  const { versionId } = useParams<{ versionId: string }>();
  const id = versionId!;

  const anchorQuery = useQuery({
    queryKey: ["anchor", id],
    queryFn: () => getAnchor(id),
    retry: (failureCount, error) => !(error instanceof ApiError && error.status === 404) && failureCount < 2,
  });

  if (anchorQuery.isLoading) return <Spinner label="Reading anchor record…" />;

  if (anchorQuery.error) {
    if (anchorQuery.error instanceof ApiError && anchorQuery.error.status === 404) {
      return <EmptyState title="Not anchored yet" hint="This version has no blockchain anchor recorded." />;
    }
    return <ErrorBanner error={anchorQuery.error} />;
  }

  const anchor = anchorQuery.data;
  if (!anchor) return null;

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-lg font-semibold text-slate-900">Blockchain Anchor Record</h1>

      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <Row label="Status" value={<StatusBadge status={anchor.status} />} />
        <Row label="Event type" value={anchor.event_type} />
        <Row label="Network" value={anchor.network} />
        <Row label="Contract address" value={<span className="font-mono">{anchor.contract_address}</span>} />
        <Row label="Transaction hash" value={<span className="font-mono">{anchor.tx_hash ?? "— pending —"}</span>} />
        <Row label="Block number" value={anchor.block_number ?? "— pending —"} />
        <Row label="Recorded hash" value={<span className="font-mono">{anchor.sha256}</span>} />
        <Row label="Created" value={formatDateTime(anchor.created_at)} />
        <Row label="Confirmed" value={formatDateTime(anchor.confirmed_at)} />
        {anchor.error && <Row label="Last error" value={anchor.error} />}
      </div>

      {anchor.onchain && (
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="mb-1 text-sm font-semibold text-slate-800">Live on-chain read</h2>
          <Row label="Exists on-chain" value={anchor.onchain.exists ? "Yes" : "No"} />
          <Row label="On-chain hash" value={<span className="font-mono">{anchor.onchain.hash}</span>} />
          <Row label="Block timestamp" value={anchor.onchain.ts} />
        </div>
      )}

      {anchor.etherscan_url && (
        <a
          href={anchor.etherscan_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
        >
          Open on Etherscan
        </a>
      )}
    </div>
  );
}
