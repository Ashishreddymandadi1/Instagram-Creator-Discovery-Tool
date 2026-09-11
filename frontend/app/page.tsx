"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, getHealth, refreshCreator, searchCreators } from "@/lib/api";
import type { HealthResponse, SearchResponse } from "@/lib/types";
import { SearchHero } from "@/components/SearchHero";
import { SearchProgress, type Stage } from "@/components/SearchProgress";
import { SearchCriteriaPanel } from "@/components/SearchCriteria";
import { ResultsList } from "@/components/ResultsList";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { WarningBanner } from "@/components/WarningBanner";

export default function Page() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState<Stage>("parsing");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastBrief, setLastBrief] = useState<string>("");
  const [refreshingId, setRefreshingId] = useState<number | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  const runSearch = useCallback(async (brief: string) => {
    setLoading(true);
    setError(null);
    setData(null);
    setLastBrief(brief);

    // The backend runs the whole pipeline in one request and does not stream
    // lifecycle events. These stages are client-side loading indicators that
    // represent the major pipeline steps; they advance on a coarse timer and the
    // last one holds until the real response lands. "done" is set only in the
    // finally block below, i.e. only when the API call actually returns.
    setStage("parsing");
    const t1 = setTimeout(() => setStage("discovering"), 1500);
    const t2 = setTimeout(() => setStage("analyzing"), 5000);
    const t3 = setTimeout(() => setStage("ranking"), 12000);

    try {
      const res = await searchCreators(brief, 8);
      setData(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unexpected error. Please try again.");
    } finally {
      [t1, t2, t3].forEach(clearTimeout);
      setStage("done");
      setLoading(false);
    }
  }, []);

  const handleRefresh = useCallback(
    async (id: number) => {
      setRefreshingId(id);
      try {
        const res = await refreshCreator(id);
        setData((prev) =>
          prev
            ? {
                ...prev,
                results: prev.results.map((c) => (c.id === id ? res.creator : c)),
              }
            : prev,
        );
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Refresh failed.");
      } finally {
        setRefreshingId(null);
      }
    },
    [],
  );

  return (
    <main className="mx-auto max-w-3xl px-5 py-10 sm:py-14">
      <SearchHero onSearch={runSearch} loading={loading} />

      {health && !health.llm_configured && (
        <p className="mt-4 rounded-lg border border-bad/30 bg-bad/10 px-4 py-2 text-xs text-frost/90">
          Backend reports the LLM is not configured. Set ANTHROPIC_API_KEY in backend/.env.
        </p>
      )}

      <div className="mt-8 space-y-5">
        {loading && <SearchProgress stage={stage} />}

        {!loading && error && (
          <ErrorState message={error} onRetry={lastBrief ? () => runSearch(lastBrief) : undefined} />
        )}

        {!loading && !error && data && (
          <>
            <SearchCriteriaPanel criteria={data.criteria} />
            <WarningBanner warnings={data.warnings} />
            {data.results.length > 0 ? (
              <ResultsList
                results={data.results}
                candidateCount={data.candidate_count}
                onRefresh={handleRefresh}
                refreshingId={refreshingId}
              />
            ) : (
              <EmptyState message="No credible Instagram creators were found for this brief. Try broadening the topics." />
            )}
          </>
        )}

        {!loading && !error && !data && <EmptyState />}
      </div>

      <footer className="mt-14 border-t border-ink-800 pt-6 text-xs text-ghost">
        <p>
          Scoring: GEO/Search 35% · Topics 30% · Content 25% · Creator Fit 10% —
          computed deterministically by the backend. No follower or engagement
          numbers are shown unless they come from real evidence.
        </p>
        {health && (
          <p className="mt-1">
            Backend: LLM {health.llm_model} · providers{" "}
            {health.search_providers.join(", ") || "none"} · cache{" "}
            {health.cache_ttl_hours}h
          </p>
        )}
      </footer>
    </main>
  );
}
