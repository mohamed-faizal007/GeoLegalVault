import { statusTone, TONE_BADGE } from "../lib/status";

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${TONE_BADGE[statusTone(status)]}`}
    >
      {status.replaceAll("_", " ")}
    </span>
  );
}
