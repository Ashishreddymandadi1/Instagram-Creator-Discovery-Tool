# Architecture

## Components

| Component | Where | Responsibility |
|---|---|---|
| **Frontend** | `frontend/` (Next.js App Router, TS, Tailwind) | One page: brief input, a staged loading indicator (client-side representation of the pipeline — the backend does not stream stage events), criteria panel, ranked creator cards, score breakdown, evidence, refresh. Knows only `NEXT_PUBLIC_API_BASE_URL`. |
| **API** | `backend/app/api/` (FastAPI) | `/api/health`, `/api/search`, `/api/creators/{id}`, `/api/creators/{id}/refresh`. Validates input, maps errors to safe messages. |
| **Query Parser** | `services/query_parser.py` | Brief → `SearchCriteria` via the LLM (`prompts.build_brief_parse_messages`). Deterministic keyword fallback if the LLM is unavailable. |
| **Discovery Providers** | `providers/` | `SearchProvider` ABC. **`SerperSearchProvider` is the currently active live provider.** `TavilySearchProvider`, `BraveSearchProvider` and `OptionalNoKeyProvider` are fully implemented, retained, and one env var away from being active (opt in via `SEARCH_PROVIDERS`). `registry.build_providers()` returns those listed *and* holding a key. |
| **Instagram URL layer** | `providers/instagram_url.py` | Normalize to `https://www.instagram.com/<handle>/`, extract handle, reject non-profile paths (`p`, `reel(s)`, `explore`, `stories`, `accounts`, hashtags, login). |
| **Evidence Enrichment** | `services/enrichment_service.py` | Group evidence per candidate, extract a best-effort display name from titles, run a few bounded follow-up queries for thin candidates. |
| **LLM Analysis** | `services/analysis_service.py` + `llm_service.py` | One batched call classifying a bounded set of candidates against the rubric, evidence-only. Returns `evidence_indices` per creator. Malformed rows dropped, not fatal. Output validated with `LLMCreatorAnalysis`. |
| **Scoring** | `services/scoring_service.py` | `calculate_relevance_score(geo, topic, content, fit)` — fixed weights, clamp 0–100, round. Pure and fully unit-tested. |
| **Deduplication** | `services/deduplication.py` | `build_candidates()` filters to valid profile URLs and groups evidence by normalized lowercase handle. Also `resolve_evidence_indices()` — validates the LLM's `evidence_indices` (drop negative / out-of-range, dedupe). |
| **Persistence / Cache** | `services/creator_service.py` + `database.py` | SQLite tables `creator`, `creator_evidence`, `creator_analysis`, **`analysis_evidence`**, `search_run`, `search_result`. `link_analysis_evidence()` ties an analysis to the exact evidence rows that supported it. 24h TTL cache keyed on the normalized brief. |
| **Orchestrator** | `services/search_orchestrator.py` | Ties the pipeline together for `run_search` and `refresh_creator`; assigns `data_status`; enforces the 5–10 shortlist bounds without padding. |

## Search sequence

```mermaid
sequenceDiagram
    participant U as User
    participant F as Next.js
    participant A as FastAPI
    participant G as LLM
    participant P as Serper
    participant DB as SQLite

    U->>F: enter brief, click "Find Creators"
    F->>A: POST /api/search { brief, limit }
    Note over F: staged loading indicator advances on a client timer<br/>(no server-streamed events); "done" waits for the response
    A->>DB: fresh cached run for this brief?
    alt cache hit (< TTL)
        DB-->>A: stored ranked results + analysis-scoped evidence
        A-->>F: results (data_status = "cached")
    else
        A->>G: parse brief -> SearchCriteria
        G-->>A: topics, geo_related_topics, creator_types, search_queries
        A->>P: run queries concurrently (bounded)
        P-->>A: web results
        A->>A: filter to IG profile URLs, dedupe by handle, cap for analysis
        A->>P: targeted follow-up queries for thin candidates
        P-->>A: more evidence
        A->>G: batched creator analysis (evidence only, rubric)
        G-->>A: component scores + explanation + evidence_indices per creator
        A->>A: deterministic overall score, rank desc, take top 5-10
        A->>DB: upsert creators + evidence; save analyses; link AnalysisEvidence
        A-->>F: results (data_status = "live" | "partial")
    end
    F-->>U: ranked shortlist with score breakdown + analysis-scoped evidence

    U->>F: click "Refresh" on a card
    F->>A: POST /api/creators/{id}/refresh
    A->>P: re-discover evidence for that handle
    A->>G: re-analyze
    A->>DB: new analysis row + its own AnalysisEvidence links (old analysis untouched)
    A-->>F: updated creator
```

## Evidence model

```
Creator
   ├── CreatorEvidence            reusable search results, accrued over time
   └── CreatorAnalysis            one brief → one evaluation (4 signals + score)
          └── AnalysisEvidence  → CreatorEvidence
                                   the exact sources that supported THIS score
```

The LLM is sent a candidate's evidence as a numbered list and returns
`evidence_indices`. `resolve_evidence_indices()` sanitizes them (negatives and
out-of-range dropped, deduplicated); `link_analysis_evidence()` then writes one
`AnalysisEvidence` row per selected source. If nothing valid remains, it falls
back to *all* evidence that was supplied to that analysis — never to unrelated
historical evidence. `to_creator_result()` reads evidence only through these
links, so a result (including a cached replay) shows exactly the provenance of
the analysis that produced its score.

## The candidate funnel

```
Serper discovery
   → up to MAX_CANDIDATES (24) valid, deduplicated Instagram candidates
     ── this is the API's `candidate_count` and the UI's "N candidates discovered"
   → first MAX_ANALYSIS_CANDIDATES (14) sent to the LLM for semantic analysis + rubric scoring
   → deterministic weighted scoring + rank
   → top DEFAULT_RESULT_LIMIT (8, bounded 5–10) returned ── the API's `returned_count`
```

`candidate_count` is the number *discovered*, not the number analyzed. There is
no separate "analyzed count" in the API contract for this case study; the cap is
`MAX_ANALYSIS_CANDIDATES` and discovery order front-loads the strongest queries.

## Design choices

- **The LLM classifies, the backend scores.** The LLM is good at reading evidence
  and judging signals; it is not a trustworthy calculator or a source of ground
  truth. The overall number is always `scoring_service`'s.
- **One batched analysis call** per search (plus one parse call) over a bounded
  candidate set (`MAX_ANALYSIS_CANDIDATES`) keeps cost and latency down and stays
  within a reasonable per-call token budget. If the LLM is briefly
  rate-limited, the orchestrator serves the last real results for that brief
  (labelled `cached`) rather than failing.
- **Provider abstraction** means the active search provider (Serper) can be replaced with a licensed
  creator-data source without touching discovery, scoring, or the API.
- **Analysis-scoped evidence** — provenance follows the analysis, not the creator.
- **`data_status` everywhere** so the UI never implies freshness it doesn't have.
- **Bounded everything**: ≤ `MAX_SEARCH_QUERIES` LLM-generated queries, ≤ `MAX_CANDIDATES`
  candidates collected, ≤ `MAX_ANALYSIS_CANDIDATES` sent to the LLM, ≤ 5 concurrent
  outbound requests, ≤ `MAX_RESULT_LIMIT` results.
