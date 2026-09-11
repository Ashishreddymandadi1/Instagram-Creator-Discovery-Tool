import type { Evidence } from "@/lib/types";

export function EvidencePanel({ evidence }: { evidence: Evidence[] }) {
  if (!evidence.length) {
    return <p className="text-xs text-ghost">No evidence was recorded for this creator.</p>;
  }
  return (
    <ul className="space-y-2.5">
      {evidence.map((e, i) => (
        <li key={i} className="rounded-lg border border-ink-700 bg-ink-950/50 p-3">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-ghost">
            <span className="rounded bg-ink-800 px-1.5 py-0.5">{e.source_provider}</span>
            {e.synthetic && <span className="text-warn">synthetic</span>}
            <span>· {new Date(e.retrieved_at).toLocaleDateString()}</span>
          </div>
          {e.title && <p className="mt-1 text-sm text-frost/90">{e.title}</p>}
          {e.snippet && <p className="mt-0.5 text-xs text-ghost">{e.snippet}</p>}
          <a
            href={e.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-1 inline-block break-all text-xs text-signal hover:underline"
          >
            {e.source_url}
          </a>
        </li>
      ))}
    </ul>
  );
}
