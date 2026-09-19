import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { getVerifyHistory, runVerify, type VerificationResult } from "../api/verify";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import { formatDateTime } from "../lib/format";

const RESULT_STYLES: Record<VerificationResult, string> = {
  VERIFIED: "bg-emerald-500/10 border-emerald-400/30 text-emerald-200",
  MISMATCH: "bg-red-500/10 border-red-400/30 text-red-200",
  NOT_ANCHORED: "bg-white/5 border-white/15 text-ink/90",
};

const RESULT_ICON_STYLES: Record<VerificationResult, string> = {
  VERIFIED: "bg-emerald-500/20 text-emerald-300",
  MISMATCH: "bg-red-500/20 text-red-300",
  NOT_ANCHORED: "bg-white/10 text-muted",
};

const RESULT_HEADLINE: Record<VerificationResult, string> = {
  VERIFIED: "VERIFIED",
  MISMATCH: "MISMATCH — tamper detected",
  NOT_ANCHORED: "NOT ANCHORED YET",
};

const RESULT_ICON_PATH: Record<VerificationResult, string> = {
  VERIFIED: "m5 13 4 4L19 7",
  MISMATCH: "M6 6l12 12M18 6 6 18",
  NOT_ANCHORED: "M6 12h12",
};

function ResultIcon({ result }: { result: VerificationResult }) {
  return (
    <span className={`flex h-12 w-12 items-center justify-center rounded-full ${RESULT_ICON_STYLES[result]}`}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6" aria-hidden="true">
        <path d={RESULT_ICON_PATH[result]} />
      </svg>
    </span>
  );
}

function HashRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-white/10 py-2.5 last:border-0">
      <span className="text-xs uppercase tracking-wide text-faint">{label}</span>
      <span className="break-all font-mono text-xs text-ink/90">{value ?? "— not available —"}</span>
    </div>
  );
}

export default function Verification() {
  const { versionId } = useParams<{ versionId: string }>();
  const id = versionId!;
  const queryClient = useQueryClient();

  const historyQuery = useQuery({
    queryKey: ["verify-history", id],
    queryFn: () => getVerifyHistory(id),
  });

  const verifyMutation = useMutation({
    mutationFn: () => runVerify(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["verify-history", id] }),
  });

  const freshResult = verifyMutation.data;
  const lastRecord = historyQuery.data?.items[0];

  const display = freshResult
    ? {
        result: freshResult.result,
        recomputed: freshResult.recomputed,
        stored: freshResult.stored,
        onchain: freshResult.onchain,
        txHash: freshResult.tx_hash,
        etherscanUrl: freshResult.etherscan_url,
      }
    : lastRecord
      ? {
          result: lastRecord.result,
          recomputed: lastRecord.recomputed_hash,
          stored: lastRecord.stored_hash,
          onchain: lastRecord.onchain_hash,
          txHash: null as string | null,
          etherscanUrl: null as string | null,
        }
      : null;

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Integrity Verification</h1>
        <p className="mt-0.5 text-sm text-muted">
          Recomputes the SHA-256 of the stored file and compares it against the hash saved at
          upload time and the hash anchored on-chain.
        </p>
      </div>

      <button type="button" onClick={() => verifyMutation.mutate()} disabled={verifyMutation.isPending} className="btn-primary">
        {verifyMutation.isPending ? "Verifying…" : "Run verification"}
      </button>

      {verifyMutation.error && <ErrorBanner error={verifyMutation.error} />}

      {display && (
        <div className={`flex flex-col items-center gap-3 rounded-lg border-2 p-6 text-center shadow-sm ${RESULT_STYLES[display.result]}`}>
          <ResultIcon result={display.result} />
          <p className="text-2xl font-bold tracking-wide">{RESULT_HEADLINE[display.result]}</p>
        </div>
      )}

      {display && (
        <div className="card-pad">
          <h2 className="mb-1 text-sm font-semibold text-ink">3-way hash comparison</h2>
          <HashRow label="Recomputed (current file bytes)" value={display.recomputed} />
          <HashRow label="Stored (recorded at upload)" value={display.stored} />
          <HashRow label="On-chain (Sepolia)" value={display.onchain} />
          {display.txHash && (
            <div className="mt-3">
              <a
                href={display.etherscanUrl ?? "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-medium text-brand-400 underline hover:text-brand-300"
              >
                View transaction on Etherscan
              </a>
            </div>
          )}
          {!display.txHash && (
            <p className="mt-2 text-xs text-faint">
              Run a fresh verification above to see the transaction link for this result.
            </p>
          )}
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <h2 className="text-sm font-semibold text-ink">Verification history</h2>
        </div>
        {historyQuery.isLoading && <Spinner label="Loading history…" />}
        {historyQuery.error && (
          <div className="p-4">
            <ErrorBanner error={historyQuery.error} />
          </div>
        )}
        {historyQuery.data && historyQuery.data.items.length === 0 && (
          <p className="px-4 py-6 text-sm text-faint">No verification runs yet.</p>
        )}
        {historyQuery.data && historyQuery.data.items.length > 0 && (
          <ul className="divide-y divide-white/10">
            {historyQuery.data.items.map((record) => (
              <li key={record.id} className="flex items-center justify-between px-4 py-2.5 text-sm">
                <span className={`font-medium ${record.result === "VERIFIED" ? "text-emerald-300" : record.result === "MISMATCH" ? "text-red-300" : "text-muted"}`}>
                  {record.result}
                </span>
                <span className="text-xs text-faint">{formatDateTime(record.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <Link to={`/versions/${id}/blockchain`} className="link-muted text-xs">
        View full blockchain anchor record →
      </Link>
    </div>
  );
}
