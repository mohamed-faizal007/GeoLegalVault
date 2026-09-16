export default function EmptyState({
  title,
  hint,
}: {
  title: string;
  hint?: string;
}) {
  return (
    <div className="rounded-md border border-dashed border-slate-300 px-6 py-10 text-center">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        className="mx-auto h-8 w-8 text-slate-300"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M4 7h16v12a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7Zm0 0 2-4h12l2 4M9 12h6"
        />
      </svg>
      <p className="mt-3 text-sm font-medium text-slate-600">{title}</p>
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </div>
  );
}
