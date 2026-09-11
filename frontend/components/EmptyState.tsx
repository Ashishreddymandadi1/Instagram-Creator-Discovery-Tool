export function EmptyState({ message }: { message?: string }) {
  return (
    <div className="rounded-xl border border-ink-700 bg-ink-900 px-6 py-14 text-center">
      <p className="text-frost font-medium">No creators to show yet</p>
      <p className="mt-1 text-sm text-ghost">
        {message ?? "Enter a brief above and run a search to build a shortlist."}
      </p>
    </div>
  );
}
