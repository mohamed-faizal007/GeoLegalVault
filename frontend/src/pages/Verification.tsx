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

const RESULT_HEADLINE: Record<VerificationResult, string> = {
  VERIFIED: "VERIFIED",
  MISMATCH: "MISMATCH — tamper detected",
  NOT_ANCHORED: "NOT ANCHORED YET",
};

function HashRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-slate-100 py-2 last:border-0">
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
        <h1 className="text-lg font-semibold text-slate-900">Integrity Verification</h1>
        <p className="text-sm text-slate-500">
          Recomputes the SHA-256 of the stored file and compares it against the hash saved at
          upload time and the hash anchored on-chain.
        </p>
      </div>

      <button
        type="button"
        onClick={() => verifyMutation.mutate()}
        disabled={verifyMutation.isPending}
        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
      >
        {verifyMutation.isPending ? "Verifying…" : "Run verification"}
      </button>

      {verifyMutation.error && <ErrorBanner error={verifyMutation.error} />}

      {display && (
        <div className={`rounded-lg border-2 p-6 text-center ${RESULT_STYLES[display.result]}`}>
          <p className="text-2xl font-bold tracking-wide">{RESULT_HEADLINE[display.result]}</p>
        </div>
      )}

      {display && (
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
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
                className="text-xs font-medium text-slate-600 underline"
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

      <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-4 py-3">
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
              <li key={record.id} className="flex items-center justify-between px-4 py-2 text-sm">
                <span className={`font-medium ${record.result === "VERIFIED" ? "text-emerald-600" : record.result === "MISMATCH" ? "text-red-600" : "text-slate-500"}`}>
                  {record.result}
                </span>
                <span className="text-xs text-slate-400">{formatDateTime(record.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <Link to={`/versions/${id}/blockchain`} className="text-xs text-slate-500 hover:underline">
        View full blockchain anchor record →
      </Link>
    </div>
  );
}
