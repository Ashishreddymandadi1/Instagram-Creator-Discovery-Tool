"use client";

import type { CreatorResult } from "@/lib/types";
import { CreatorCard } from "./CreatorCard";

interface Props {
  results: CreatorResult[];
  candidateCount: number;
  onRefresh: (id: number) => void;
  refreshingId: number | null;
}

export function ResultsList({ results, candidateCount, onRefresh, refreshingId }: Props) {
  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between text-xs text-ghost">
        <span>
          <span className="text-frost">{results.length}</span> creator
          {results.length === 1 ? "" : "s"} shortlisted
        </span>
        <span title="Valid Instagram profiles discovered via search. A bounded subset of these is sent to the LLM for analysis and scoring.">
          {candidateCount} candidates discovered
        </span>
      </div>
      <div className="space-y-4">
        {results.map((c, i) => (
          <CreatorCard
            key={c.id}
            creator={c}
            rank={i + 1}
            onRefresh={onRefresh}
            refreshing={refreshingId === c.id}
          />
        ))}
      </div>
    </section>
  );
}
