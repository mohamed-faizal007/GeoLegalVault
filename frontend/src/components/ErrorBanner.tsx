import { describeError } from "../lib/errorMessages";

/** Renders WHY an action failed — auth, role, or location — using the
 * server's structured error code (Phase 9 brief), never a generic failure. */
export default function ErrorBanner({ error }: { error: unknown }) {
  if (!error) return null;
  const { code, message } = describeError(error);
  return (
    <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <p className="font-medium">{message}</p>
      <p className="mt-0.5 text-xs text-red-500">Error code: {code}</p>
    </div>
  );
}
