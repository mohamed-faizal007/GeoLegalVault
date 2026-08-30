const STATUS_STYLES: Record<string, string> = {
  DRAFT: "bg-slate-100 text-slate-700",
  SUBMITTED: "bg-blue-100 text-blue-700",
  UNDER_REVIEW: "bg-blue-100 text-blue-700",
  PENDING_APPROVAL: "bg-amber-100 text-amber-700",
  CHANGES_REQUESTED: "bg-amber-100 text-amber-700",
  APPROVED: "bg-teal-100 text-teal-700",
  BLOCKCHAIN_ANCHORED: "bg-teal-100 text-teal-700",
  ACTIVE: "bg-emerald-100 text-emerald-700",
  AMENDMENT_REQUESTED: "bg-amber-100 text-amber-700",
  SUPERSEDED: "bg-slate-100 text-slate-500",
  ARCHIVED: "bg-slate-200 text-slate-600",
  TAMPERED: "bg-red-100 text-red-700",
  VERIFIED: "bg-emerald-100 text-emerald-700",
  MISMATCH: "bg-red-100 text-red-700",
  NOT_ANCHORED: "bg-slate-100 text-slate-600",
  PENDING: "bg-amber-100 text-amber-700",
  CONFIRMED: "bg-emerald-100 text-emerald-700",
  FAILED: "bg-red-100 text-red-700",
};

export default function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? "bg-slate-100 text-slate-700";
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${style}`}>
      {status.replaceAll("_", " ")}
    </span>
  );
}
