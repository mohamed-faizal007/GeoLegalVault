export default function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2.5 py-6 text-sm text-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/15 border-t-brand-400" />
      {label}
    </div>
  );
}
