export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-xl border border-bad/30 bg-bad/10 px-6 py-8 text-center">
      <p className="font-medium text-bad">Something went wrong</p>
      <p className="mt-1 text-sm text-frost/80">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 rounded-lg border border-ink-700 bg-ink-800 px-4 py-2 text-sm text-frost hover:border-signal/60"
        >
          Try again
        </button>
      )}
    </div>
  );
}
