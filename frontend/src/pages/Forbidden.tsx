import { Link } from "react-router-dom";

export default function Forbidden() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
      <h1 className="text-lg font-semibold text-slate-900">You don't have permission to view this page</h1>
      <p className="text-sm text-slate-500">Your account's role doesn't include this feature.</p>
      <Link to="/" className="mt-2 text-sm font-medium text-slate-700 underline">
        Back to Dashboard
      </Link>
    </div>
  );
}
