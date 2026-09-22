import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  approveDocument,
  archiveDocument,
  downloadDocument,
  getDocument,
  listVersions,
  reviewDocument,
  submitDocument,
} from "../api/documents";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import StatusBadge from "../components/StatusBadge";
import { useAuth } from "../context/useAuth";
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
    default: "btn-secondary",
    primary: "btn-primary",
    danger: "btn-danger",
  };
  return (
    <button type="button" disabled={pending} onClick={onClick} className={styles[variant]}>
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

  // The version being processed is the highest version_no — the same rule the
  // backend uses. Its uploader can neither review nor approve it (maker != checker),
  // and only its uploader may submit it (D-016) — so we fetch versions when
  // any of those could apply.
  const roleForQueue = user?.role;
  const maybeCheckable =
    (docQuery.data?.status === "SUBMITTED" &&
      hasPermission(roleForQueue, PERMISSIONS.REVIEW_PERFORM)) ||
    (docQuery.data?.status === "PENDING_APPROVAL" &&
      hasPermission(roleForQueue, PERMISSIONS.APPROVE_PERFORM));
  const maybeSubmittable =
    docQuery.data?.status === "DRAFT" && hasPermission(roleForQueue, PERMISSIONS.DOCUMENT_SUBMIT);
  const versionsQuery = useQuery({
    queryKey: ["versions", documentId],
    queryFn: () => listVersions(documentId),
    enabled: maybeCheckable || maybeSubmittable,
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

  const versions = versionsQuery.data?.items ?? [];
  const latestVersion = versions.reduce<(typeof versions)[number] | null>(
    (best, v) => (best === null || v.version_no > best.version_no ? v : best),
    null,
  );
  // Fail closed while versions load: no button beats a button that will 403.
  const isUploader = latestVersion !== null && latestVersion.uploaded_by === user?.id;
  const checkerReady = latestVersion !== null && !isUploader;
  // Submit is authorized by the current version's uploader, not
  // document.owner_id (D-016) — an amendment/correction can be uploaded by
  // someone other than the document's original owner.
  const canSubmit =
    doc.status === "DRAFT" &&
    isUploader &&
    hasPermission(role, PERMISSIONS.DOCUMENT_SUBMIT);
  const canReview =
    doc.status === "SUBMITTED" && hasPermission(role, PERMISSIONS.REVIEW_PERFORM) && checkerReady;
  const canApprove =
    doc.status === "PENDING_APPROVAL" &&
    hasPermission(role, PERMISSIONS.APPROVE_PERFORM) &&
    checkerReady;
  const blockedAsUploader = maybeCheckable && isUploader;
  const blockedFromSubmit =
    maybeSubmittable && latestVersion !== null && !isUploader;
  const canAmend = doc.status === "ACTIVE" && hasPermission(role, PERMISSIONS.DOCUMENT_AMEND);
  // Amendment was requested but the corrected file hasn't been uploaded yet —
  // the amend page shows the upload form in this state.
  const canUploadAmendment =
    doc.status === "AMENDMENT_REQUESTED" && hasPermission(role, PERMISSIONS.DOCUMENT_AMEND);
  // A2 (D-015/D-017): changes were requested, looping the document back to
  // DRAFT — the amend page's upload form also accepts a corrected file here.
  const canUploadCorrection =
    doc.status === "DRAFT" &&
    doc.review_feedback != null &&
    hasPermission(role, PERMISSIONS.DOCUMENT_AMEND);
  // Backend only archives ACTIVE documents (workflow.archive); SUPERSEDED would 409.
  const canArchive = doc.status === "ACTIVE" && hasPermission(role, PERMISSIONS.DOCUMENT_ARCHIVE);
  const canDownload = !!doc.current_version_id && hasPermission(role, PERMISSIONS.DOCUMENT_VIEW);
  const canVerify = !!doc.current_version_id && hasPermission(role, PERMISSIONS.VERIFY_PERFORM);

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-ink">{doc.title}</h1>
          <StatusBadge status={doc.status} />
          {doc.integrity_flag === "TAMPERED" && <StatusBadge status="TAMPERED" />}
        </div>
        <p className="mt-0.5 text-sm text-muted">
          {doc.doc_type} — {doc.classification}
        </p>
      </div>

      {doc.integrity_flag === "TAMPERED" && (
        <div className="rounded-md border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          A verification run detected that the stored file no longer matches its approved hash.
          See the Verification page for details.
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 card-pad text-sm md:grid-cols-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-faint">Owner</p>
          <p className="mt-0.5 text-ink/90">{doc.owner_id}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-faint">Created</p>
          <p className="mt-0.5 text-ink/90">{formatDateTime(doc.created_at)}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-faint">Updated</p>
          <p className="mt-0.5 text-ink/90">{formatDateTime(doc.updated_at)}</p>
        </div>
        <div className="col-span-2 md:col-span-3">
          <p className="text-xs uppercase tracking-wide text-faint">Tags</p>
          <p className="mt-0.5 text-ink/90">{doc.tags.length ? doc.tags.join(", ") : "—"}</p>
        </div>
      </div>

      {doc.review_feedback && doc.status === "DRAFT" && (
        <div
          role="note"
          className="rounded-md border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100"
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-300">
            Changes requested · {formatDateTime(doc.review_feedback.reviewed_at)}
          </p>
          <p className="mt-1 whitespace-pre-wrap">{doc.review_feedback.comment}</p>
        </div>
      )}

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
        {canUploadAmendment && (
          <ActionButton
            label="Upload amended version"
            variant="primary"
            onClick={() => navigate(`/documents/${documentId}/amend`)}
          />
        )}
        {canUploadCorrection && (
          <ActionButton
            label="Upload corrected file"
            variant="primary"
            onClick={() => navigate(`/documents/${documentId}/amend`)}
          />
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
        <Link to={`/documents/${documentId}/versions`} className="btn-secondary">
          Version history
        </Link>
      </div>

      {blockedAsUploader && (
        <p className="text-sm text-muted">
          You uploaded this version, so someone else must {doc.status === "SUBMITTED" ? "review" : "approve"} it.
        </p>
      )}
      {blockedFromSubmit && (
        <p className="text-sm text-muted">
          Only whoever uploaded the current version can submit it for review.
        </p>
      )}

      {reviewOpen && (
        <div className="card-pad">
          <h2 className="text-sm font-semibold text-ink">Review decision</h2>
          <textarea
            value={reviewComment}
            onChange={(e) => setReviewComment(e.target.value)}
            placeholder="Comment (required if requesting changes) — visible to everyone who can view this document; no personal data"
            className="input mt-2"
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
