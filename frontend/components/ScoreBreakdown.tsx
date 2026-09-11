import { SCORE_WEIGHTS, type ScoreBreakdown } from "@/lib/types";

function barColor(v: number) {
  if (v >= 70) return "bg-good";
  if (v >= 40) return "bg-warn";
  return "bg-bad";
}

export function ScoreBreakdownPanel({ breakdown }: { breakdown: ScoreBreakdown }) {
  return (
    <div className="space-y-2.5 rounded-lg border border-ink-700 bg-ink-950/50 p-3.5">
      <p className="text-xs font-medium text-ghost">Why this score?</p>
      {SCORE_WEIGHTS.map(({ key, label, weight }) => {
        const v = breakdown[key];
        return (
          <div key={key} className="space-y-1">
            <div className="flex items-baseline justify-between text-xs">
              <span className="text-frost/85">
                {label} <span className="text-ghost">· {weight}%</span>
              </span>
              <span className="tabular-nums text-frost">{v}</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-ink-800">
              <div className={"h-full rounded-full " + barColor(v)} style={{ width: `${v}%` }} />
            </div>
          </div>
        );
      })}
      <p className="pt-1 text-[11px] leading-relaxed text-ghost">
        Overall = geo·0.35 + topic·0.30 + content·0.25 + fit·0.10, computed by the
        backend. The LLM scores each signal against a fixed rubric; it never returns
        the overall number.
      </p>
    </div>
  );
}
