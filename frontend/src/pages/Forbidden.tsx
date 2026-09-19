import { Link } from "react-router-dom";

export default function Forbidden() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
      <span className="mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-amber-500/10 text-amber-300 ring-1 ring-inset ring-amber-400/30">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="h-6 w-6" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v.01M12 3 2 20h20L12 3Z" />
        </svg>
      </span>
      <h1 className="text-lg font-semibold text-ink">You don't have permission to view this page</h1>
      <p className="text-sm text-muted">Your account's role doesn't include this feature.</p>
      <Link to="/" className="btn-secondary btn-sm mt-2">
        Back to Dashboard
      </Link>
    </div>
  );
}
