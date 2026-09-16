import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { getVerifyHistory, runVerify, type VerificationResult } from "../api/verify";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import { formatDateTime } from "../lib/format";

const RESULT_STYLES: Record<VerificationResult, string> = {
  VERIFIED: "bg-emerald-50 border-emerald-300 text-emerald-800",
  MISMATCH: "bg-red-50 border-red-300 text-red-800",
  NOT_ANCHORED: "bg-slate-50 border-slate-300 text-slate-700",
};

const RESULT_ICON_STYLES: Record<VerificationResult, string> = {
  VERIFIED: "bg-emerald-100 text-emerald-600",
  MISMATCH: "bg-red-100 text-red-600",
  NOT_ANCHORED: "bg-slate-200 text-slate-500",
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
    <div className="flex flex-col gap-0.5 border-b border-slate-100 py-2.5 last:border-0">
      <span className="text-xs uppercase tracking-wide text-slate-400">{label}</span>
      <span className="break-all font-mono text-xs text-slate-700">{value ?? "— not available —"}</span>
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
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Integrity Verification</h1>
        <p className="mt-0.5 text-sm text-slate-500">
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
          <h2 className="mb-1 text-sm font-semibold text-slate-800">3-way hash comparison</h2>
          <HashRow label="Recomputed (current file bytes)" value={display.recomputed} />
          <HashRow label="Stored (recorded at upload)" value={display.stored} />
          <HashRow label="On-chain (Sepolia)" value={display.onchain} />
          {display.txHash && (
            <div className="mt-3">
              <a
                href={display.etherscanUrl ?? "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-medium text-brand-600 underline hover:text-brand-700"
              >
                View transaction on Etherscan
              </a>
            </div>
          )}
          {!display.txHash && (
            <p className="mt-2 text-xs text-slate-400">
              Run a fresh verification above to see the transaction link for this result.
            </p>
          )}
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <h2 className="text-sm font-semibold text-slate-800">Verification history</h2>
        </div>
        {historyQuery.isLoading && <Spinner label="Loading history…" />}
        {historyQuery.error && (
          <div className="p-4">
            <ErrorBanner error={historyQuery.error} />
          </div>
        )}
        {historyQuery.data && historyQuery.data.items.length === 0 && (
          <p className="px-4 py-6 text-sm text-slate-400">No verification runs yet.</p>
        )}
        {historyQuery.data && historyQuery.data.items.length > 0 && (
          <ul className="divide-y divide-slate-100">
            {historyQuery.data.items.map((record) => (
              <li key={record.id} className="flex items-center justify-between px-4 py-2.5 text-sm">
                <span className={`font-medium ${record.result === "VERIFIED" ? "text-emerald-600" : record.result === "MISMATCH" ? "text-red-600" : "text-slate-500"}`}>
                  {record.result}
                </span>
                <span className="text-xs text-slate-400">{formatDateTime(record.created_at)}</span>
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
