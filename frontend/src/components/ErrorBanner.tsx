import { describeError } from "../lib/errorMessages";

/** Renders WHY an action failed — auth, role, or location — using the
 * server's structured error code (Phase 9 brief), never a generic failure. */
export default function ErrorBanner({ error }: { error: unknown }) {
  if (!error) return null;
  const { code, message } = describeError(error);
  return (
    <div className="flex items-start gap-2.5 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.75}
        className="mt-0.5 h-4 w-4 shrink-0 text-red-500"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="9" />
        <path strokeLinecap="round" d="M12 8v5M12 16h.01" />
      </svg>
      <div>
        <p className="font-medium">{message}</p>
        <p className="mt-0.5 text-xs text-red-500">Error code: {code}</p>
      </div>
    </div>
  );
}
