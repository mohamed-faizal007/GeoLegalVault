import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
      <h1 className="text-lg font-semibold text-slate-900">Page not found</h1>
      <Link to="/" className="mt-2 text-sm font-medium text-slate-700 underline">
        Back to Dashboard
      </Link>
    </div>
  );
}
