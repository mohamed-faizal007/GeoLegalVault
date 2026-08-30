import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { getDocument, listVersions } from "../api/documents";
import ErrorBanner from "../components/ErrorBanner";
import EmptyState from "../components/EmptyState";
import Spinner from "../components/Spinner";
import StatusBadge from "../components/StatusBadge";
import { formatBytes, formatDateTime, truncateHash } from "../lib/format";

export default function VersionHistory() {
  const { id } = useParams<{ id: string }>();
  const documentId = id!;

  const docQuery = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => getDocument(documentId),
  });
  const versionsQuery = useQuery({
    queryKey: ["versions", documentId],
    queryFn: () => listVersions(documentId),
  });

  return (
    <div className="max-w-3xl space-y-4">
      <div>
        <Link to={`/documents/${documentId}`} className="text-xs text-slate-500 hover:underline">
          ← Back to document
        </Link>
        <h1 className="mt-1 text-lg font-semibold text-slate-900">
          Version history{docQuery.data ? `: ${docQuery.data.title}` : ""}
        </h1>
      </div>

      {versionsQuery.isLoading && <Spinner label="Loading versions…" />}
      {versionsQuery.error && <ErrorBanner error={versionsQuery.error} />}
      {versionsQuery.data && versionsQuery.data.items.length === 0 && (
        <EmptyState title="No versions yet" />
      )}

      {versionsQuery.data && versionsQuery.data.items.length > 0 && (
        <ol className="space-y-3">
          {[...versionsQuery.data.items]
            .sort((a, b) => b.version_no - a.version_no)
            .map((version) => (
              <li
                key={version.id}
                className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-slate-800">V{version.version_no}</span>
                    <StatusBadge status={version.status} />
                    {version.anchored && <StatusBadge status="CONFIRMED" />}
                  </div>
                  <span className="text-xs text-slate-400">{formatDateTime(version.uploaded_at)}</span>
                </div>
                <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-500 md:grid-cols-4">
                  <div>
                    <dt className="uppercase text-slate-400">SHA-256</dt>
                    <dd className="font-mono">{truncateHash(version.sha256)}</dd>
                  </div>
                  <div>
                    <dt className="uppercase text-slate-400">Size</dt>
                    <dd>{formatBytes(version.size_bytes)}</dd>
                  </div>
                  <div>
                    <dt className="uppercase text-slate-400">MIME</dt>
                    <dd>{version.mime}</dd>
                  </div>
                  <div>
                    <dt className="uppercase text-slate-400">Prev. hash</dt>
                    <dd className="font-mono">
                      {version.prev_version_hash ? truncateHash(version.prev_version_hash) : "—"}
                    </dd>
                  </div>
                </dl>
                <div className="mt-3 flex gap-2">
                  <Link
                    to={`/verify/${version.id}`}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
                  >
                    Verify
                  </Link>
                  {version.anchored && (
                    <Link
                      to={`/versions/${version.id}/blockchain`}
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
                    >
                      View on-chain
                    </Link>
                  )}
                </div>
              </li>
            ))}
        </ol>
      )}
    </div>
  );
}
