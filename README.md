# GEO Creator Scout

AI-assisted Instagram creator discovery for GEO (Generative Engine Optimization) outreach.

## What it does

You type a brief in plain English, e.g.:

> *Find Instagram creators who cover AI, marketing, entrepreneurship, or emerging
> technology and could be relevant to our GEO Playbook.*

The tool turns that into structured search criteria, discovers real Instagram
creator profiles, grounds every pick in evidence from web search, classifies
each candidate against a fixed rubric, and returns a **shortlist of 5–10
creators** with a deterministic, explainable score.

## Output

Each result includes:

- **Name / handle**
- **Instagram URL** (normalized, real profile link)
- **Relevant content topics**
- **A 0–100 relevance score**, with an expandable breakdown
- **A short explanation** of why the creator is a fit
- **Evidence** the recommendation is based on (source, title, snippet, link)

## Architecture

```
Brief
  ↓  LLM query understanding (topics, GEO themes, search queries)
Creator discovery (Instagram profile URLs only; posts/reels/explore rejected)
  ↓
Evidence collection (search snippets; targeted follow-ups for thin candidates)
  ↓
LLM classification (evidence-only; returns per-signal scores, not the total)
  ↓
Deterministic scoring (backend-computed, fixed weights)
  ↓
Top 5–10 creators
```

Frontend: Next.js (App Router, TypeScript, Tailwind). Backend: FastAPI +
Pydantic + SQLAlchemy + SQLite. Full detail: [docs/architecture.md](docs/architecture.md).

## Scoring

| Component | Weight | What it measures |
|---|---|---|
| GEO / Search Relevance | **35%** | Tie to GEO / AI-search / SEO-for-AI themes |
| Topic Relevance | **30%** | Overlap with the topics in *your* brief |
| Content Relevance | **25%** | Whether the creator actually *creates* content on the subject |
| Creator Fit | **10%** | Educator / analyst / founder / thought-leader signal (not follower count) |

```
overall_score = round(
    geo_search_relevance * 0.35
  + topic_relevance      * 0.30
  + content_relevance    * 0.25
  + creator_fit          * 0.10
)
```

Every component is clamped to 0–100; the LLM classifies the four signals
against a documented rubric, but **the backend always computes the final
score** — the LLM never returns the overall number. A creator must also clear
a credibility gate (`MIN_RELEVANCE_SCORE`, `MIN_RESULT_CONFIDENCE`) to make the
shortlist — weak matches are excluded outright, never padded in to hit a
minimum count. Rubric + worked example:
[docs/scoring.md](docs/scoring.md).

## Data quality

This tool **never invents data**. No fabricated follower counts, engagement
rates, verification status, locations, or post history. Unavailable fields are
`null` / "Not available". Every recommendation carries the search evidence it
was actually derived from, scoped to the specific analysis that produced its
score (a cached result shows exactly the evidence that earned that score, not
every source ever seen for that creator).

## Setup

**Prerequisites:** Python 3.11+, Node.js 18+.

### Backend

```bash
cd backend
python -m venv .venv
```

Activate it (Windows PowerShell: `.venv\Scripts\Activate.ps1`; Windows CMD:
`.venv\Scripts\activate.bat`; macOS/Linux: `source .venv/bin/activate`), then:

```bash
pip install -r requirements.txt
cp .env.example .env        # fill in — see "Environment variables"
uvicorn app.main:app --reload --port 8000
```

Backend runs at `http://localhost:8000` (`/docs` for the OpenAPI UI). SQLite is
created automatically on first run.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Environment variables

### `backend/.env`

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | **yes** | LLM provider API key |
| `ANTHROPIC_MODEL` | no | LLM model id (default: a fast/cheap model) |
| `SERPER_API_KEY` | **yes** | Active search provider (Google SERP via Serper.dev) |
| `SEARCH_PROVIDERS` | no | Priority order of search providers (default: `serper`) |
| `CACHE_TTL_HOURS` | no | How long a cached search stays fresh (default: `24`) |
| `MAX_SEARCH_QUERIES` | no | Cap on discovery queries per search (default: `6`) |
| `MAX_CANDIDATES` | no | Cap on candidates collected before analysis (default: `24`) |
| `MAX_ANALYSIS_CANDIDATES` | no | Candidates sent to the LLM for scoring (default: `14`) |
| `DEFAULT_RESULT_LIMIT` / `MIN_` / `MAX_` | no | Shortlist size bounds (default `8`, bounded `5`–`10`) |
| `MIN_RELEVANCE_SCORE` | no | Credibility gate: minimum overall score to make the shortlist (default `40`) |
| `MIN_RESULT_CONFIDENCE` | no | Credibility gate: minimum LLM confidence to make the shortlist (default `0.35`) |
| `DATABASE_URL` | no | SQLite path |
| `CORS_ORIGINS` | no | Allowed frontend origins |

A second search-provider implementation (Tavily) and an optional Brave/keyless
fallback are included in the codebase and can be enabled by setting their key
and adding them to `SEARCH_PROVIDERS` — no code changes required.

### `frontend/.env.local`

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Backend base URL (default `http://localhost:8000`) |

No secrets live in the frontend or are ever returned by `/api/health` — only
booleans.

## Testing

```bash
cd backend
pytest -q                       # unit tests, ~90% coverage
```

All tests use in-memory fakes for the LLM and search providers
(`FakeLLM`, `FakeProvider` in `tests/conftest.py`) — **no external API calls or
credits are consumed** by the test suite or CI.

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Status + booleans (`llm_configured`, active `search_providers`) |
| `POST` | `/api/search` | `{ brief, limit?, force_refresh? }` → ranked shortlist |
| `GET` | `/api/creators/{id}` | Latest stored analysis for one creator |
| `POST` | `/api/creators/{id}/refresh` | Re-discover evidence and re-score one creator |

## Limitations

- Public web-search indexing doesn't guarantee complete Instagram coverage; a
  strong niche creator may not be indexed for a given query.
- Indexed titles/snippets can be stale.
- Direct Instagram post history, follower counts and engagement are not
  available to this prototype by design (no scraping, no login).
- LLM classification isn't bit-for-bit deterministic across calls; the scoring
  formula and rubric are fixed, so identical signals always produce the same
  overall score.

## Production evolution

The `SearchProvider` abstraction is the seam for evolving past free-tier web
search toward a licensed/approved creator-data provider or an official
platform API, with scheduled refresh, changed-content detection, and
per-field provenance. Full plan: [docs/production-data-strategy.md](docs/production-data-strategy.md).

## License

MIT — see [LICENSE](LICENSE).
