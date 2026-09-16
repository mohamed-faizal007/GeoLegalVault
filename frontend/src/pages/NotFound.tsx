import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
      <p className="text-4xl font-bold text-slate-200">404</p>
      <h1 className="text-lg font-semibold text-slate-900">Page not found</h1>
      <Link to="/" className="btn-secondary btn-sm mt-2">
        Back to Dashboard
      </Link>
    </div>
  );
}
