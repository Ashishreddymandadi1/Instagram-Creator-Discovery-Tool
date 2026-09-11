# Production Data Strategy

How GEO Creator Scout would source and keep real creator data fresh if taken
past the prototype. The prototype deliberately uses free web-search APIs; this
document is about what changes for production.

## 1. Provider abstraction (already in place)

`backend/app/providers/base.py` defines `SearchProvider`. Discovery, enrichment,
scoring and the API depend on the abstraction, not on the specific active provider (currently Tavily). Production adds new
implementations behind the same interface:

- `LicensedCreatorDataProvider` — a paid creator-database API (see §3)
- `OfficialPlatformProvider` — Instagram Graph API where a business relationship
  and permissions exist (see §4)
- keep `TavilySearchProvider` (and optionally `SerperSearchProvider`) as a
  discovery-only supplement

`registry.build_providers()` already selects providers by configuration; a
production deployment just changes `SEARCH_PROVIDERS` and adds keys.

## 2. Approved search APIs

For discovery (finding *candidates*), keep using licensed SERP/web-search APIs
(Tavily, Serper, Brave, Bing, Google Programmable Search) under their commercial
terms, with attribution where required. These are fine for "who might be
relevant"; they are **not** a system of record for profile facts.

## 3. Licensed creator-data providers

For profile facts (name, bio, category, recent post themes, audience size where
permitted), integrate a licensed influencer/creator-data vendor
(e.g. Modash, HypeAuditor, Phyllo, Favikon-class APIs). These vendors handle
platform agreements, refresh, and compliance. GEO Creator Scout would:

- call them only for shortlisted candidates (cost control)
- store a `source_provider` + `retrieved_at` on every field
- still run GEO classification itself (the vendors don't do GEO)

## 4. Official platform APIs

The **Instagram Graph API** exposes data only for (a) accounts you manage or
(b) business/creator accounts that have authorized your app, plus limited
business-discovery for public professional accounts. Use it where a creator has
opted in (e.g. a managed outreach programme). Never scrape, never automate login,
never rotate proxies to evade rate limits.

## 5. Periodic refresh

Discovery and enrichment are separate refresh problems:

| What | Cadence | Why (design choice, not a universal truth) |
|---|---|---|
| **Discovery** (new candidates for a saved brief) | weekly | New creators emerge slowly; daily re-discovery mostly re-finds the same profiles |
| **Shortlisted / high-value creators** | daily or on-demand | These are the ones a human will contact; staleness here is expensive |
| **Evaluated-but-not-selected** | every 2–4 weeks | Cheap to skip; revisit before a new campaign |
| **Inactive / rejected** | quarterly or never | Low value; only refresh if a brief changes |

Cadences are configurable per brief and per creator tier, not hard-coded.

## 6. `last_updated` timestamps

Every creator, every evidence item, and every analysis already carries a
timestamp. The API returns `last_updated` and `data_status`; the UI shows
"updated N min/hr/days ago". Production keeps this and adds per-field timestamps
from licensed providers.

## 7. TTL-based caching

Already implemented: `CACHE_TTL_HOURS` (default 24). A search for an identical
brief within the TTL replays stored **real** results labelled `cached`. Beyond
the TTL it re-runs. Production would make TTL a function of creator tier (§5) and
add a background refresh job so cache misses are rare during business hours.

## 8. Changed-content detection

Store a content fingerprint per creator (hash of the concatenated evidence
titles/snippets, or embeddings of recent post captions from a licensed feed). On
refresh:

- fingerprint unchanged → keep the existing analysis, just bump `retrieved_at`
  (no LLM call — saves cost)
- fingerprint changed → re-run LLM analysis and re-score
- score moved by more than a threshold → flag for human review

## 9. Rate limits

- Bounded concurrency (already: 5 concurrent outbound requests)
- Per-provider token buckets with the provider's documented RPM/RPD
- Exponential backoff with jitter on 429 (the Anthropic SDK already retries; add the
  same for data providers)
- A daily spend/quota ceiling per provider; when hit, degrade to cache + queue
  refreshes for the next window

## 10. Retries

- Idempotent GETs: retry up to 3× with backoff
- LLM JSON: already retries and then degrades (`llm_service.complete_json`)
- Never retry a non-idempotent write blindly; use the `search_run` row as an
  idempotency anchor

## 11. Data provenance

Every displayed fact must answer "where did this come from and when":

```
Evidence { source_provider, source_url, title, snippet, retrieved_at, synthetic }
```

Provenance is **scoped to the analysis**, not the creator. `Creator` accumulates
reusable `CreatorEvidence` over many searches; each `CreatorAnalysis` (one brief →
one evaluation) links, via `AnalysisEvidence`, to only the evidence that supported
*that* score. So a result — even a cached replay from an earlier search — shows
the sources behind its own number, never every source ever seen for the creator.
Production keeps this model and extends `CreatorEvidence` with licensed-provider
facts (provider name, licence reference, fetch time), still linked per analysis
and surfaced in the evidence panel and any exported report.

## 12. Stale data

- `data_status` never lies: `live`, `cached`, `partial`.
- If the newest evidence for a shortlisted creator is older than a threshold, the
  card shows a "may be stale — refresh" hint.
- Exports include the retrieval date next to every creator.

## 13. Deletion & privacy

- Honour platform deletion: if a profile 404s on refresh, mark it
  `removed` and stop showing it; purge its stored evidence after a grace period.
- Right-to-erasure: a `DELETE /api/creators/{id}` that hard-deletes the creator,
  its evidence and analyses (cascade already modelled).
- Store only what's needed for outreach relevance; no audience PII, no scraped
  private data, no follower lists.
- Keep a record of the lawful basis / licence for each data source.

## 14. Cost control

- LLM: 1 parse + 1 batched analysis per search; refresh is 1 + 1 per creator.
  Batching keeps this ~2 calls regardless of shortlist size.
- Search APIs: capped queries (`MAX_SEARCH_QUERIES`) and candidates
  (`MAX_CANDIDATES`); enrichment queries are capped separately.
- Licensed data providers: called only for shortlisted creators, cached hard.
- Background refresh runs off-peak; interactive requests prefer cache.
- Per-brief and per-tenant budgets with alerting.

## Proposed production architecture

```
                    ┌─────────────── Scheduled refresh workers ───────────────┐
                    │  weekly: re-discover per saved brief                     │
                    │  daily:  refresh shortlisted creators (fingerprint gate) │
                    └───────────────┬─────────────────────────────────────────┘
                                    │
User → Next.js → API ──► Orchestrator ──► Provider registry
                                    │        ├─ LicensedCreatorDataProvider  (facts)
                                    │        ├─ SERP providers               (discovery)
                                    │        └─ OfficialPlatformProvider     (opted-in)
                                    │
                                    ├──► LLM classification (fingerprint-gated)
                                    ├──► Deterministic scoring (unchanged)
                                    └──► Postgres (creators, evidence w/ provenance,
                                          analyses, briefs, refresh log) + object store
```

The scoring engine, GEO playbook, and API contract stay exactly as they are; only
the data sources and the refresh loop change.
