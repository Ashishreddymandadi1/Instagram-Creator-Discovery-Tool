export function WarningBanner({ warnings }: { warnings: string[] }) {
  if (!warnings.length) return null;
  return (
    <div className="rounded-lg border border-warn/30 bg-warn/10 px-4 py-3 text-sm text-frost/90">
      <ul className="space-y-1">
        {warnings.map((w, i) => (
          <li key={i} className="flex gap-2">
            <span className="text-warn">!</span>
            <span>{w}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
