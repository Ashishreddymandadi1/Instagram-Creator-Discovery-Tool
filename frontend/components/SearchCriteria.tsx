import type { SearchCriteria as Criteria } from "@/lib/types";

function Chips({ label, items, tone }: { label: string; items: string[]; tone: "topic" | "geo" }) {
  if (!items.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs uppercase tracking-wide text-ghost">{label}</span>
      {items.map((t) => (
        <span
          key={t}
          className={
            "rounded-full px-2.5 py-1 text-xs " +
            (tone === "geo"
              ? "border border-signal/30 bg-signal/10 text-signal"
              : "border border-ink-700 bg-ink-800 text-frost/85")
          }
        >
          {t}
        </span>
      ))}
    </div>
  );
}

export function SearchCriteriaPanel({ criteria }: { criteria: Criteria }) {
  return (
    <div className="space-y-2.5 rounded-xl border border-ink-700 bg-ink-900/60 p-4">
      <Chips label="Searching for" items={criteria.topics} tone="topic" />
      <Chips label="GEO focus" items={criteria.geo_related_topics} tone="geo" />
      {criteria.creator_types.length > 0 && (
        <Chips label="Creator types" items={criteria.creator_types} tone="topic" />
      )}
    </div>
  );
}
