"use client";

import { useState } from "react";
import type { CreatorResult } from "@/lib/types";
import { ScoreBreakdownPanel } from "./ScoreBreakdown";
import { EvidencePanel } from "./EvidencePanel";

const STATUS_LABEL: Record<CreatorResult["data_status"], string> = {
  live: "Live",
  cached: "Cached",
  partial: "Partial",
  demo: "Synthetic demo data",
};

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "unknown";
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} hr ago`;
  return `${Math.round(hrs / 24)} d ago`;
}

function scoreColor(score: number): string {
  if (score >= 70) return "text-good";
  if (score >= 45) return "text-warn";
  return "text-bad";
}

interface Props {
  creator: CreatorResult;
  rank: number;
  onRefresh: (id: number) => void;
  refreshing: boolean;
}

export function CreatorCard({ creator, rank, onRefresh, refreshing }: Props) {
  const [showScore, setShowScore] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);

  return (
    <article className="animate-rise rounded-xl border border-ink-700 bg-ink-900 p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs text-ghost">
            <span className="rounded bg-ink-800 px-1.5 py-0.5 tabular-nums">#{rank}</span>
            <span>{STATUS_LABEL[creator.data_status]}</span>
            <span>· updated {relativeTime(creator.last_updated)}</span>
          </div>
          <h3 className="mt-1.5 truncate text-lg font-semibold text-frost">
            {creator.name ?? creator.handle}
          </h3>
          <a
            href={creator.instagram_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-signal hover:underline"
          >
            {creator.handle}
          </a>
        </div>
        <div className="shrink-0 text-right">
          <div className={"text-3xl font-semibold tabular-nums " + scoreColor(creator.score)}>
            {creator.score}
            <span className="text-base text-ghost">/100</span>
          </div>
          <div className="text-[11px] text-ghost">
            confidence {Math.round(creator.confidence * 100)}%
          </div>
        </div>
      </div>

      {creator.relevant_topics.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {creator.relevant_topics.map((t) => (
            <span
              key={t}
              className="rounded-full border border-ink-700 bg-ink-800 px-2 py-0.5 text-xs text-frost/85"
            >
              {t}
            </span>
          ))}
        </div>
      )}

      <p className="mt-3 text-sm leading-relaxed text-frost/85">{creator.content_summary}</p>

      <div className="mt-3 rounded-lg border border-ink-700 bg-ink-950/40 p-3">
        <p className="text-xs font-medium text-ghost">Why this creator</p>
        <p className="mt-1 text-sm leading-relaxed text-frost/90">{creator.explanation}</p>
      </div>

      {creator.warnings.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs text-warn">
          {creator.warnings.map((w, i) => (
            <li key={i}>! {w}</li>
          ))}
        </ul>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <a
          href={creator.instagram_url}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg bg-signal px-3.5 py-2 text-xs font-medium text-ink-950 hover:bg-signal/90"
        >
          View Instagram
        </a>
        <button
          onClick={() => onRefresh(creator.id)}
          disabled={refreshing}
          className="rounded-lg border border-ink-700 bg-ink-800 px-3.5 py-2 text-xs text-frost hover:border-signal/60 disabled:opacity-50"
        >
          {refreshing ? "Refreshing…" : "Refresh"}
        </button>
        <button
          onClick={() => setShowScore((v) => !v)}
          className="rounded-lg border border-ink-700 bg-ink-800 px-3.5 py-2 text-xs text-frost hover:border-signal/60"
        >
          {showScore ? "Hide score breakdown" : "Score breakdown"}
        </button>
        <button
          onClick={() => setShowEvidence((v) => !v)}
          className="rounded-lg border border-ink-700 bg-ink-800 px-3.5 py-2 text-xs text-frost hover:border-signal/60"
        >
          Evidence ({creator.evidence.length}) {showEvidence ? "▴" : "▾"}
        </button>
      </div>

      {showScore && (
        <div className="mt-3">
          <ScoreBreakdownPanel breakdown={creator.score_breakdown} />
        </div>
      )}
      {showEvidence && (
        <div className="mt-3">
          <EvidencePanel evidence={creator.evidence} />
        </div>
      )}
    </article>
  );
}
