"use client";

import { useState } from "react";

const EXAMPLE =
  "Find Instagram creators who cover AI, marketing, entrepreneurship, or emerging technology and could be relevant to our GEO Playbook.";

interface Props {
  onSearch: (brief: string) => void;
  loading: boolean;
}

export function SearchHero({ onSearch, loading }: Props) {
  const [brief, setBrief] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = brief.trim();
    if (trimmed.length >= 3 && !loading) onSearch(trimmed);
  }

  return (
    <header className="space-y-5">
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-signal">
          GEO Creator Scout
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-frost sm:text-4xl">
          Discover Instagram creators who can amplify a GEO Playbook
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-ghost">
          Describe who you want in plain language. The tool turns your brief into
          search criteria, discovers real Instagram creators, grounds every pick in
          evidence, and ranks them with an explainable GEO relevance score.
        </p>
      </div>

      <form onSubmit={submit} className="space-y-3">
        <textarea
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          rows={3}
          maxLength={600}
          placeholder={EXAMPLE}
          className="w-full resize-y rounded-xl border border-ink-700 bg-ink-900 px-4 py-3 text-sm text-frost placeholder:text-ghost/60 focus:border-signal/60 focus:outline-none"
        />
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={loading || brief.trim().length < 3}
            className="rounded-lg bg-signal px-5 py-2.5 text-sm font-medium text-ink-950 transition hover:bg-signal/90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? "Searching…" : "Find Creators"}
          </button>
          <button
            type="button"
            onClick={() => setBrief(EXAMPLE)}
            disabled={loading}
            className="text-xs text-ghost underline-offset-2 hover:text-frost hover:underline disabled:opacity-40"
          >
            Use the example brief
          </button>
          <span className="ml-auto text-xs text-ghost">{brief.length}/600</span>
        </div>
      </form>
    </header>
  );
}
