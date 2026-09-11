# 5-Minute Demo Script

Two terminals running before you start:

```bash
# terminal 1
cd backend && uvicorn app.main:app --reload --port 8000
# terminal 2
cd frontend && npm run dev
```

Browser at `http://localhost:3000`. Have `docs/scoring.md` open in a tab.

---

## 0:00–0:30 — The problem

> "A GEO Playbook — our guide to optimizing for AI search engines like ChatGPT
> Search, Perplexity and Google AI Overviews — is only valuable if the right
> creators discuss and share it. The task: given a plain-English brief, produce a
> shortlist of 5–10 Instagram creators who'd plausibly care, each with a score
> and a defensible reason. This tool does that."

## 0:30–1:00 — Architecture (one breath)

> "Next.js frontend, FastAPI backend, SQLite. The brief goes to the LLM, which turns
> it into search criteria. We run those through Tavily, scoped to instagram.com
> only, keep only real Instagram profile URLs, collect the search snippets as evidence, and send that evidence
> back to the LLM to classify each creator against a fixed rubric — and it tells us
> which evidence items support each judgement. Then **our backend** — not the
> LLM — computes the final score with fixed weights. Every recommendation carries
> the exact sources behind its score, and we never invent a number we don't
> have."

## 1:00–1:30 — Enter the brief

Click **"Use the example brief"** → it fills:

> *Find Instagram creators who cover AI, marketing, entrepreneurship, or emerging
> technology and could be relevant to our GEO Playbook.*

Click **Find Creators**.

> "While it runs you see a staged loading indicator for the pipeline —
> understanding the brief, discovering creators, analyzing GEO relevance,
> ranking. It's one backend request doing all of that live (LLM + Tavily), so
> it takes 15–50 seconds — the LLM's batched analysis is the slower step. The stages are client-side; the backend doesn't stream
> events, and the app only shows 'done' when the request actually returns."

## 1:30–3:15 — Walk the results

When results land, point at the **criteria panel** first:

> "The LLM pulled these topics from my sentence — AI, marketing, entrepreneurship,
> emerging technology — and mapped them to GEO themes: AI search, Generative
> Engine Optimization, AI Overviews. These weren't hard-coded; a different brief
> gives different criteria."

The header says "*N candidates discovered*". If asked what that means:

> "Tavily discovers up to 24 valid Instagram profiles. The first 14 of those go
> to the LLM for the semantic analysis and rubric scoring — that keeps one batched
> call a reasonable size and cost. Then deterministic scoring ranks them
> and we return the top 5–10. So it's: **up to 24 discovered → up to 14 analyzed
> and scored → top 5–10 returned.** The number on screen is the discovered count,
> not the analyzed count."

Then the **top card**:

> "Number one, [name / handle], score [N] out of 100. Topics as chips. This
> one-line summary and the 'Why this creator' paragraph are written by the LLM **from
> the evidence only** — I told it explicitly not to invent jobs, follower counts,
> or bios."

Click **View Instagram** on one card → opens the real profile in a new tab.

> "That's a real, normalized profile URL — `instagram.com/handle/`. Posts, reels
> and hashtag pages are rejected during discovery."

Note the absence of fake metrics:

> "No follower count, no engagement rate. A naive version synthesizes those when
> they're missing — this one shows nothing rather than something false."

## 3:15–4:00 — "Why this score?"

Click **Score breakdown** on the top card.

> "Four signals: GEO/Search 35%, Topic 30%, Content 25%, Creator Fit 10%. The LLM
> scored each from the evidence against a written rubric. The overall is
> `geo·0.35 + topic·0.30 + content·0.25 + fit·0.10`, rounded — computed by the
> backend. So if GEO relevance is 15 and topic is 80, I can tell you exactly why
> the total is what it is. The LLM can't just hand me 'score: 92' and be trusted."

Click **Evidence** on the same card.

> "And here's the provenance — the search provider, the result title and snippet,
> and a link. Every live recommendation is backed by this."

## 4:00–4:30 — Refresh one creator

Click **Refresh** on any card.

> "This re-runs discovery for just that creator, re-analyzes with fresh evidence,
> re-scores, and updates the card — without touching the others. In production
> you'd refresh high-value creators daily and everyone else weekly."

(Optionally: re-run the same brief → note it returns instantly and labelled
**Cached** — the 24h cache, and the demo-reliability fallback.)

## 4:30–5:00 — Production data & close

> "In production the search-provider slot is swapped for a licensed creator-data
> API or an official platform API where creators have opted in — same interface,
> the scoring engine doesn't change. Refresh runs on a schedule with
> changed-content detection so we don't re-pay the LLM for unchanged profiles, and
> every field carries provenance and a timestamp. The GEO definitions live in one
> editable JSON file, so pointing this at the real GEO Playbook is a config
> change, not a rewrite."

> "Tests: 107 of them, ~90% coverage — the scoring formula, URL parsing, dedupe,
> provider-failure handling, and the no-fabrication guarantee are all covered."

---

## If something fails live

- **Search returns < 5**: that's the honest path — point at the warning banner:
  *"it found what it could and didn't pad the list."*
- **LLM rate-limited**: re-run; the SDK retries automatically.
  Or use a brief you've run before → instant **Cached** results.
- **Provider timeout**: the app continues with whatever provider responded and
  shows a `partial` status.
