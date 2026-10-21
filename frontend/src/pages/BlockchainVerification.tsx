import { useQuery } from "@tanstack/react-query";
import { Check, CircleAlert, Copy, ExternalLink, MinusCircle, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useParams } from "react-router-dom";

import { getAnchor } from "../api/blockchain";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import StatusBadge from "../components/StatusBadge";
import { ApiError } from "../api/http";
import { formatDateTime } from "../lib/format";
import { compareHashes, COMPARISON_TEXT, type HashComparison } from "../lib/hashCompare";

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-white/10 py-2 last:border-0">
      <span className="text-xs uppercase tracking-wide text-faint">{label}</span>
      <span className="break-all text-sm text-ink/90">{value}</span>
    </div>
  );
}

// Each outcome has its own icon and its own words; the colour only reinforces them.
const TONE: Record<HashComparison, { box: string; icon: ReactNode }> = {
  MATCH: {
    box: "border-emerald-400/40 bg-emerald-500/10 text-emerald-200",
    icon: <Check size={18} aria-hidden="true" />,
  },
  MISMATCH: {
    box: "border-red-400/40 bg-red-500/10 text-red-200",
    icon: <X size={18} aria-hidden="true" />,
  },
  NOT_ON_CHAIN: {
    box: "border-amber-400/40 bg-amber-500/10 text-amber-200",
    icon: <CircleAlert size={18} aria-hidden="true" />,
  },
  UNAVAILABLE: {
    box: "border-white/15 bg-white/5 text-muted",
    icon: <MinusCircle size={18} aria-hidden="true" />,
  },
};

/** Copy to the clipboard, with a visible "Copied" so the click is never a silent no-op. */
function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }
  return (
    <button type="button" onClick={copy} className="btn-secondary btn-sm" aria-label={label}>
      <Copy size={14} aria-hidden="true" />
      {copied ? "Copied" : "Copy"}
    </button>
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

  const comparison = compareHashes(anchor);
  const tone = TONE[comparison];
  const text = COMPARISON_TEXT[comparison];
  const networkLabel = anchor.network_label ?? anchor.network;

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Blockchain Anchor Record</h1>
        <span className="inline-flex items-center rounded-full bg-white/5 px-2.5 py-0.5 text-xs font-medium text-muted ring-1 ring-inset ring-white/10">
          {networkLabel}
        </span>
      </div>

      <section aria-labelledby="hash-compare-title" className="card-pad space-y-3">
        <h2 id="hash-compare-title" className="text-sm font-semibold text-ink">
          Recorded hash vs live on-chain hash
        </h2>
        <div role="status" className={`flex items-start gap-2 rounded-lg border px-3 py-2 ${tone.box}`}>
          <span className="mt-0.5 shrink-0">{tone.icon}</span>
          <div>
            <p className="text-sm font-semibold" data-testid="hash-comparison">
              {text.label}
            </p>
            <p className="text-xs opacity-90">{text.detail}</p>
          </div>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-wide text-faint">Recorded hash (database)</p>
            <p className="mt-1 break-all rounded-md bg-black/20 p-2 font-mono text-xs text-ink/90">
              {anchor.sha256}
            </p>
          </div>
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-wide text-faint">On-chain hash (read live)</p>
            <p className="mt-1 break-all rounded-md bg-black/20 p-2 font-mono text-xs text-ink/90">
              {anchor.onchain
                ? anchor.onchain.exists
                  ? anchor.onchain.hash
                  : "— none on chain —"
                : "— not read —"}
            </p>
          </div>
        </div>
        {anchor.onchain?.exists && (
          <p className="text-xs text-muted">Block timestamp {anchor.onchain.ts}</p>
        )}
      </section>

      <div className="card-pad">
        <Row label="Status" value={<StatusBadge status={anchor.status} />} />
        <Row label="Event type" value={anchor.event_type} />
        <Row
          label="Network"
          value={
            <>
              {networkLabel}{" "}
              <span className="text-xs text-faint">(chain id {anchor.chain_id ?? "unknown"})</span>
            </>
          }
        />
        <Row label="Contract address" value={<span className="font-mono">{anchor.contract_address}</span>} />
        <Row
          label="Transaction hash"
          value={
            anchor.tx_hash ? (
              <span className="flex flex-col gap-2">
                <span className="font-mono">{anchor.tx_hash}</span>
                <span className="flex flex-wrap items-center gap-2">
                  <CopyButton text={anchor.tx_hash} label="Copy transaction hash" />
                  {anchor.etherscan_url ? (
                    <a
                      href={anchor.etherscan_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-secondary btn-sm"
                    >
                      <ExternalLink size={14} aria-hidden="true" />
                      View on Etherscan ({networkLabel})
                    </a>
                  ) : (
                    <span className="text-xs text-muted">
                      No block explorer link: this chain is not Sepolia.
                    </span>
                  )}
                </span>
              </span>
            ) : (
              "— pending —"
            )
          }
        />
        <Row label="Block number" value={anchor.block_number ?? "— pending —"} />
        <Row label="Created" value={formatDateTime(anchor.created_at)} />
        <Row label="Confirmed" value={formatDateTime(anchor.confirmed_at)} />
        {anchor.error && <Row label="Last error" value={anchor.error} />}
      </div>
    </div>
  );
}
