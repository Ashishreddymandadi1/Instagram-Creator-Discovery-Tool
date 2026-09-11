"use client";

/**
 * Staged loading indicator for the search request.
 *
 * The backend executes the entire pipeline (brief parsing → discovery →
 * enrichment → LLM analysis → scoring → ranking) inside a single HTTP request
 * and does not emit per-stage events. These labels are a representation of that
 * pipeline shown while the one request is in flight; the parent advances them on
 * a timer. Only the parent's "done" state reflects a real backend event (the API
 * response). A production version could stream real job progress via SSE or a
 * job-status endpoint.
 */
export type Stage = "parsing" | "discovering" | "analyzing" | "ranking" | "done";

const STAGES: { key: Stage; label: string }[] = [
  { key: "parsing", label: "Understanding brief" },
  { key: "discovering", label: "Discovering creators" },
  { key: "analyzing", label: "Analyzing GEO relevance" },
  { key: "ranking", label: "Ranking results" },
];

const ORDER: Stage[] = ["parsing", "discovering", "analyzing", "ranking", "done"];

export function SearchProgress({ stage }: { stage: Stage }) {
  const currentIdx = ORDER.indexOf(stage);
  return (
    <div className="space-y-3 rounded-xl border border-ink-700 bg-ink-900 p-5">
      {STAGES.map((s) => {
        const idx = ORDER.indexOf(s.key);
        const state = idx < currentIdx ? "done" : idx === currentIdx ? "active" : "pending";
        return (
          <div key={s.key} className="flex items-center gap-3 text-sm">
            <span
              className={
                "grid h-5 w-5 place-items-center rounded-full border text-xs " +
                (state === "done"
                  ? "border-good/50 bg-good/15 text-good"
                  : state === "active"
                    ? "border-signal/50 bg-signal/15 text-signal"
                    : "border-ink-700 text-ghost")
              }
            >
              {state === "done" ? "\u2713" : state === "active" ? "\u2026" : ""}
            </span>
            <span className={state === "pending" ? "text-ghost" : "text-frost"}>{s.label}</span>
            {state === "active" && (
              <span className="ml-1 h-1.5 w-1.5 animate-pulse rounded-full bg-signal" />
            )}
          </div>
        );
      })}
      <p className="pt-1 text-xs text-ghost">
        Live discovery + LLM analysis usually takes 15–50 seconds.
      </p>
    </div>
  );
}
