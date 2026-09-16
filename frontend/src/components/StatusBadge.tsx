const STATUS_STYLES: Record<string, string> = {
  DRAFT: "bg-slate-100 text-slate-600 ring-slate-500/20",
  SUBMITTED: "bg-blue-50 text-blue-700 ring-blue-600/20",
  UNDER_REVIEW: "bg-blue-50 text-blue-700 ring-blue-600/20",
  PENDING_APPROVAL: "bg-amber-50 text-amber-700 ring-amber-600/20",
  CHANGES_REQUESTED: "bg-amber-50 text-amber-700 ring-amber-600/20",
  APPROVED: "bg-teal-50 text-teal-700 ring-teal-600/20",
  BLOCKCHAIN_ANCHORED: "bg-teal-50 text-teal-700 ring-teal-600/20",
  ACTIVE: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  AMENDMENT_REQUESTED: "bg-amber-50 text-amber-700 ring-amber-600/20",
  SUPERSEDED: "bg-slate-100 text-slate-500 ring-slate-500/15",
  ARCHIVED: "bg-slate-200 text-slate-600 ring-slate-500/20",
  TAMPERED: "bg-red-50 text-red-700 ring-red-600/20",
  VERIFIED: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  MISMATCH: "bg-red-50 text-red-700 ring-red-600/20",
  NOT_ANCHORED: "bg-slate-100 text-slate-600 ring-slate-500/20",
  PENDING: "bg-amber-50 text-amber-700 ring-amber-600/20",
  CONFIRMED: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  FAILED: "bg-red-50 text-red-700 ring-red-600/20",
};

export default function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? "bg-slate-100 text-slate-700 ring-slate-500/20";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${style}`}
    >
      {status.replaceAll("_", " ")}
    </span>
  );
}
