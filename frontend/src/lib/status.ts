/**
 * One source of truth for status colour, shared by StatusBadge (the label)
 * and list rows (the left-edge accent). Colour is a scanning aid only — the
 * badge text always carries the actual status.
 */
export type StatusTone =
  | "neutral"
  | "muted"
  | "archived"
  | "info"
  | "warn"
  | "teal"
  | "success"
  | "danger";

const STATUS_TONE: Record<string, StatusTone> = {
  DRAFT: "neutral",
  SUBMITTED: "info",
  UNDER_REVIEW: "info",
  PENDING_APPROVAL: "warn",
  CHANGES_REQUESTED: "warn",
  APPROVED: "teal",
  BLOCKCHAIN_ANCHORED: "teal",
  ACTIVE: "success",
  AMENDMENT_REQUESTED: "warn",
  SUPERSEDED: "muted",
  ARCHIVED: "archived",
  TAMPERED: "danger",
  VERIFIED: "success",
  MISMATCH: "danger",
  NOT_ANCHORED: "neutral",
  PENDING: "warn",
  CONFIRMED: "success",
  FAILED: "danger",
};

export function statusTone(status: string): StatusTone {
  return STATUS_TONE[status] ?? "neutral";
}

export const TONE_BADGE: Record<StatusTone, string> = {
  neutral: "bg-white/5 text-slate-300 ring-white/15",
  muted: "bg-white/5 text-slate-400 ring-white/10",
  archived: "bg-white/10 text-slate-300 ring-white/20",
  info: "bg-blue-400/10 text-blue-300 ring-blue-400/30",
  warn: "bg-amber-400/10 text-amber-300 ring-amber-400/30",
  teal: "bg-teal-400/10 text-teal-300 ring-teal-400/30",
  success: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/30",
  danger: "bg-red-400/10 text-red-300 ring-red-400/30",
};

export const TONE_BAR: Record<StatusTone, string> = {
  neutral: "bg-slate-400",
  muted: "bg-slate-500",
  archived: "bg-slate-400",
  info: "bg-blue-400",
  warn: "bg-amber-400",
  teal: "bg-teal-400",
  success: "bg-emerald-400",
  danger: "bg-red-400",
};
