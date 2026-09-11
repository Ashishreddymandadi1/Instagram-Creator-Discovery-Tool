# Scoring

The overall relevance score is **deterministic** and computed by the backend
(`backend/app/services/scoring_service.py`). The LLM evaluates the four input
signals against the rubric below; it never returns the overall number.

## Formula

```
overall_score = round(
    geo_search_relevance * 0.35
  + topic_relevance      * 0.30
  + content_relevance    * 0.25
  + creator_fit          * 0.10
)
```

- Every component is clamped to `0–100` (non-numeric or NaN → `0`).
- The weighted sum is clamped to `0–100` and rounded to the nearest whole number.
- `calculate_relevance_score(0,0,0,0) == 0`, `calculate_relevance_score(100,100,100,100) == 100`.
- The score can never exceed 100, even if a component arrives out of range.

## Components & rubric

### 1. GEO / Search Relevance — 35%

How strongly the available **evidence** connects the creator to GEO themes.

| Band | Meaning | Example evidence |
|---|---|---|
| 80–100 | Very strong | "Generative Engine Optimization", "Answer Engine Optimization", "how to rank in Perplexity / AI Overviews", "getting cited by ChatGPT", "the future of SEO is AEO" |
| 50–79 | Related | generative AI + SEO / search marketing / content strategy / AI marketing |
| 20–49 | Weak / generic | only generic "AI" or "ChatGPT tips" with no search angle |
| 0–19 | None | no AI-search signal at all |

A creator who only mentions generic AI scores lower than one who regularly
discusses AI search or SEO.

### 2. Topic Relevance — 30%

Overlap between the creator's evidence and the topics in **the user's brief**.
Topics are derived per query by the LLM (`SearchCriteria.topics`), not assumed. For
the assignment example the topics are AI, marketing, entrepreneurship, emerging
technology — but a different brief yields different topics.

### 3. Content Relevance — 25%

Whether the evidence shows the creator actually **creates content** on the
requested subjects, versus a bare label.

| Evidence | Band |
|---|---|
| "How Google AI Overviews are changing marketing strategy" (a piece of content) | 70–100 |
| Bio says "Entrepreneur" and nothing topical | 20–40 |
| No topical content evidence | 0–20 |

### 4. Creator Fit — 10%

Does this look like an educator / analyst / founder / thought leader who would
share professional material? Signals: educational content, analysis, tutorials,
commentary, professional insights, founder expertise, regular topical posting.

- **Follower count is not used** and its absence is **not** penalized. A strong
  niche creator with no follower data is not marked down.

## Worked example

The LLM returns, from evidence, for one creator:

| Signal | Value |
|---|---|
| geo_search_relevance | 95 |
| topic_relevance | 90 |
| content_relevance | 84 |
| creator_fit | 88 |

```
95 * 0.35 = 33.25
90 * 0.30 = 27.00
84 * 0.25 = 21.00
88 * 0.10 =  8.80
            -----
            90.05  → round → 90
```

Another (the UI screenshot case): geo 15, topic 80, content 70, fit 70:

```
15*0.35 + 80*0.30 + 70*0.25 + 70*0.10
= 5.25 + 24 + 17.5 + 7 = 53.75 → 54
```

## Determinism, honestly stated

- The **formula, the weights, and the rubric definitions are fixed** and unit
  tested (`tests/test_scoring.py`).
- LLM classification is **not** mathematically deterministic across every model
  call — the same evidence may yield slightly different component scores on
  different runs (temperature 0.2, but not zero, and model-side variation).
- Therefore: the *inputs* can wobble a little; the *transformation from inputs to
  overall score* never does. Two creators with identical component scores always
  get the same overall score, and you can always see and defend the breakdown in
  the UI ("Why this score?").

## Confidence

Separate from the score, the LLM returns `confidence` (0–1) reflecting how much
evidence it had. Thin evidence → low confidence **and** lower component scores,
plus a `warnings` entry. Confidence is shown on each card; it does not feed the
score.
