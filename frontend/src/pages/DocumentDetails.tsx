import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  approveDocument,
  archiveDocument,
  downloadDocument,
  getDocument,
  reviewDocument,
  submitDocument,
} from "../api/documents";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import StatusBadge from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { getCurrentLocation } from "../hooks/useGeoLocation";
import { formatDateTime } from "../lib/format";
import { hasPermission, PERMISSIONS } from "../lib/permissions";

function ActionButton({
  label,
  onClick,
  pending,
  variant = "default",
}: {
  label: string;
  onClick: () => void;
  pending?: boolean;
  variant?: "default" | "primary" | "danger";
}) {
  const styles = {
    default: "border border-slate-300 text-slate-700 hover:bg-slate-100",
    primary: "bg-slate-900 text-white hover:bg-slate-800",
    danger: "border border-red-300 text-red-700 hover:bg-red-50",
  };
  return (
    <button
      type="button"
      disabled={pending}
      onClick={onClick}
      className={`rounded-md px-3 py-2 text-sm font-medium disabled:opacity-50 ${styles[variant]}`}
    >
      {pending ? "Working…" : label}
    </button>
  );
}

export default function DocumentDetails() {
  const { id } = useParams<{ id: string }>();
  const documentId = id!;
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewComment, setReviewComment] = useState("");
  const [actionError, setActionError] = useState<unknown>(null);

  const docQuery = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => getDocument(documentId),
  });

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["document", documentId] });
    queryClient.invalidateQueries({ queryKey: ["versions", documentId] });
  }

  const submitMutation = useMutation({
    mutationFn: () => submitDocument(documentId),
    onSuccess: invalidate,
    onError: setActionError,
  });

  const reviewMutation = useMutation({
    mutationFn: (decision: "approve" | "changes_requested") =>
      reviewDocument(documentId, decision, decision === "changes_requested" ? reviewComment : undefined),
    onSuccess: () => {
      setReviewOpen(false);
      setReviewComment("");
      invalidate();
    },
    onError: setActionError,
  });

  const approveMutation = useMutation({
    mutationFn: async () => approveDocument(documentId, await getCurrentLocation()),
    onSuccess: invalidate,
    onError: setActionError,
  });

  const archiveMutation = useMutation({
    mutationFn: () => archiveDocument(documentId),
    onSuccess: invalidate,
    onError: setActionError,
  });

  const downloadMutation = useMutation({
    mutationFn: async () => downloadDocument(documentId, await getCurrentLocation()),
    onSuccess: (res) => window.open(res.url, "_blank", "noopener,noreferrer"),
    onError: setActionError,
  });

  if (docQuery.isLoading) return <Spinner label="Loading document…" />;
  if (docQuery.error) return <ErrorBanner error={docQuery.error} />;
  if (!docQuery.data) return null;

  const doc = docQuery.data;
  const role = user?.role;
  const isOwner = user?.id === doc.owner_id;

  const canSubmit = isOwner && doc.status === "DRAFT" && hasPermission(role, PERMISSIONS.DOCUMENT_SUBMIT);
  const canReview = doc.status === "SUBMITTED" && hasPermission(role, PERMISSIONS.REVIEW_PERFORM);
  const canApprove =
    doc.status === "PENDING_APPROVAL" && hasPermission(role, PERMISSIONS.APPROVE_PERFORM);
  const canAmend = doc.status === "ACTIVE" && hasPermission(role, PERMISSIONS.DOCUMENT_AMEND);
  const canArchive =
    ["ACTIVE", "SUPERSEDED"].includes(doc.status) && hasPermission(role, PERMISSIONS.DOCUMENT_ARCHIVE);
  const canDownload = !!doc.current_version_id && hasPermission(role, PERMISSIONS.DOCUMENT_VIEW);
  const canVerify = !!doc.current_version_id && hasPermission(role, PERMISSIONS.VERIFY_PERFORM);

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-slate-900">{doc.title}</h1>
          <StatusBadge status={doc.status} />
          {doc.integrity_flag === "TAMPERED" && <StatusBadge status="TAMPERED" />}
        </div>
        <p className="text-sm text-slate-500">
          {doc.doc_type} — {doc.classification}
        </p>
      </div>

      {doc.integrity_flag === "TAMPERED" && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          A verification run detected that the stored file no longer matches its approved hash.
          See the Verification page for details.
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 rounded-lg border border-slate-200 bg-white p-4 text-sm shadow-sm md:grid-cols-3">
        <div>
          <p className="text-xs uppercase text-slate-400">Owner</p>
          <p className="text-slate-700">{doc.owner_id}</p>
        </div>
        <div>
          <p className="text-xs uppercase text-slate-400">Created</p>
          <p className="text-slate-700">{formatDateTime(doc.created_at)}</p>
        </div>
        <div>
          <p className="text-xs uppercase text-slate-400">Updated</p>
          <p className="text-slate-700">{formatDateTime(doc.updated_at)}</p>
        </div>
        <div className="col-span-2 md:col-span-3">
          <p className="text-xs uppercase text-slate-400">Tags</p>
          <p className="text-slate-700">{doc.tags.length ? doc.tags.join(", ") : "—"}</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {canSubmit && (
          <ActionButton
            label="Submit for review"
            pending={submitMutation.isPending}
            onClick={() => submitMutation.mutate()}
          />
        )}
        {canReview && (
          <ActionButton label="Review" onClick={() => setReviewOpen(true)} />
        )}
        {canApprove && (
          <ActionButton
            label="Approve"
            variant="primary"
            pending={approveMutation.isPending}
            onClick={() => approveMutation.mutate()}
          />
        )}
        {canAmend && (
          <ActionButton label="Request amendment" onClick={() => navigate(`/documents/${documentId}/amend`)} />
        )}
        {canArchive && (
          <ActionButton
            label="Archive"
            variant="danger"
            pending={archiveMutation.isPending}
            onClick={() => archiveMutation.mutate()}
          />
        )}
        {canDownload && (
          <ActionButton
            label="Download"
            pending={downloadMutation.isPending}
            onClick={() => downloadMutation.mutate()}
          />
        )}
        {canVerify && (
          <ActionButton
            label="Verify"
            variant="primary"
            onClick={() => navigate(`/verify/${doc.current_version_id}`)}
          />
        )}
        <Link
          to={`/documents/${documentId}/versions`}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
        >
          Version history
        </Link>
      </div>

      {reviewOpen && (
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-800">Review decision</h2>
          <textarea
            value={reviewComment}
            onChange={(e) => setReviewComment(e.target.value)}
            placeholder="Comment (required if requesting changes)"
            className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            rows={3}
          />
          <div className="mt-3 flex gap-2">
            <ActionButton
              label="Approve review"
              variant="primary"
              pending={reviewMutation.isPending}
              onClick={() => reviewMutation.mutate("approve")}
            />
            <ActionButton
              label="Request changes"
              pending={reviewMutation.isPending}
              onClick={() => reviewMutation.mutate("changes_requested")}
            />
            <ActionButton label="Cancel" onClick={() => setReviewOpen(false)} />
          </div>
        </div>
      )}

      {actionError !== null && <ErrorBanner error={actionError} />}
    </div>
  );
}
