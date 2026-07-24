# /agents — Multi-Agent Evidence Engine

The artifact reviewers should read. This documents how Bubble or Not gathers evidence, how agents coordinate, and why the scores are reproducible.

---

## 1. Design philosophy

**Probes, not chat loops.** A probe = one API call + one extraction → typed evidence. Agents are planned DAGs of probes, not conversational loops. More reliable, cheaper, fully traceable.

**Three intelligence layers, strictly separated:**

| Layer | Does | Never does |
|---|---|---|
| You.com research agents | open-ended gathering across their index | arithmetic, verdicts |
| Local LLM (Haiku) | bounded, rubric-anchored judgment: extraction, rhetoric/tone/hype scoring, entity resolution | free-form reasoning, scoring math |
| Our code | all arithmetic, thresholds, aggregation, signature lamps | anything requiring language understanding |

**Consequence:** identical evidence always yields identical scores. The demo is reproducible; a judge can recompute any number by hand from the evidence table.

---

## 2. Probe abstraction

```python
@dataclass(frozen=True)
class Probe:
    id: str                     # "S1-Q4", "F1-rhetoric"
    factor: str                 # f1..f6
    pattern: Literal["A", "B", "SEARCH", "QUANT"]
    endpoint: str               # search | research | finance_research | contents | fmp | yfinance
    params: dict                # query, freshness, include_domains, output_schema, ...
    cadence: Literal["run", "weekly", "monthly", "quarterly"]
    cost_estimate_usd: float
    ttl_hours: int              # skip if fresh evidence exists
    priority: int               # 1 = never drop, 3 = drop first under budget pressure
    extractor: Callable[[Any], list[Evidence]]
```

**Patterns:**
- **A** — Research API + `output_schema` (+ `source_control`). Typed JSON out, zero parsing.
- **B** — Finance Research + FINDING template → `extract()` chain. Used when the finance index matters more than native structure.
- **SEARCH** — Search API + local LLM entity/marker extraction.
- **QUANT** — FMP/yfinance, pure math, no LLM.

---

## 3. Probe registry

| Probe | Factor | Pattern | Endpoint | Cadence | ~$ | Priority |
|---|---|---|---|---|---|---|
| F5-top10 / F5-eqw / F5-200dma / F5-tnx | f5 | QUANT | fmp, yfinance | run | 0 | 1 |
| F1-rates | f1 | QUANT | fmp | run | 0 | 1 |
| F1-rhetoric | f1 | SEARCH | search(+contents) `include_domains=federalreserve.gov` | run | 0.02 | 1 |
| F2-tone-{TICKER} ×8 | f2 | B | finance_research `deep` | run | 0.11 ea | 2 |
| F2-gpu-spot | f2 | SEARCH | search + contents | run | 0.01 | 2 |
| F2-B1-strong / F2-B2-weak | f2 | A | research `standard` | run | 0.05 ea | 1 |
| F4-insider / F4-megasale | f4 | B | finance_research `deep` | run | 0.11 ea | 3 |
| F4-lockup | f4 | SEARCH | search | run | 0.01 | 3 |
| F6-narrative | f6 | SEARCH | search `count=50` + contents batch | run | 0.06 | 2 |
| S1-B1 / S1-B2 | f3 | A | research `standard` | weekly | 0.05 ea | 1 |
| S1-Q1 formation | f3 | SEARCH | search `livecrawl=news` | weekly | 0.02 | 1 |
| S1-Q2 verify ×N≤6 | f3 | A | research `standard` | weekly (fan-out) | 0.05 ea | 2 |
| S1-Q3 credit-pool | f3 | SEARCH | search | weekly | 0.01 | 3 |
| S1-Q4 destruction (canary) | f3 | SEARCH | search `livecrawl=news` | weekly | 0.02 | 1 |
| S1-Q5 ARR / S1-Q6 repricing | f3 | SEARCH | search | weekly | 0.01 ea | 2 |
| S2-B1 / S2-B2 | f3 | A | research `standard` | monthly | 0.05 ea | 1 |
| S2-Q1 formation | f3 | SEARCH | search `livecrawl=news` | monthly | 0.02 | 1 |
| S2-Q2 counterparty verify ×N | f3 | A | research `deep` `include_domains=sec.gov` | monthly | 0.10 ea | 1 |
| S2-Q3 leverage / S2-Q4 SPV | f3 | SEARCH | search | monthly | 0.01 ea | 2 |
| S2-Q5 distress (avalanche) | f3 | SEARCH | search `livecrawl=news` | monthly | 0.02 | 1 |
| S2-Q6 vendor aggregates | f3 | B | finance_research `deep` | quarterly | 0.11 | 2 |
| T-Q1 triangle legs ×3 | f3 | A | research `standard` | monthly | 0.05 ea | 3 |

Full-run cost ≈ $2.20 (all cadences due) · typical demo-day rescore ≈ $0.60 (run-cadence only, rest cached).

---

## 4. Orchestration lifecycle

```
POST /rescore (admin key) or cron
  └─ acquire asyncio.Lock            (busy → 409)
     ├─ PREFLIGHT
     │    balance = you_com.balance()
     │    probes  = registry.due(now)             # cadence filter
     │    probes  = [p for p in probes if not cache.fresh(p)]   # TTL filter
     │    if projected_cost > min(balance, RUN_BUDGET):
     │        drop lowest-priority probes; mark affected factors low_coverage
     │    write runs row (status=running)
     ├─ EXECUTE   asyncio.gather(agent(f) for f in F1..F6)
     │    per-agent: own cost ceiling + asyncio.wait_for timeout
     │    per-probe: try/except; semaphore per endpoint (search 5, research 3)
     │    every probe writes run_events + evidence rows IMMEDIATELY on completion
     ├─ REDUCE
     │    factor_results ← deterministic formulas over evidence
     │    scores         ← BTI weighted sum
     │    signatures     ← threshold + strong/weak aggregation
     └─ FINALIZE  runs row (status=done, bti, cost, elapsed)
```

**Agent shapes.** F1, F2, F4, F5, F6 are static fan-outs (probe list known at plan time). **F3 is the genuinely agentic one** — its run shape depends on what it finds:

```
Stage1Agent:
  1. S1-Q1 scan (window)                        → N articles
  2. LLM entity-extract candidate edges          → [(lab, startup, amount, date)]
  3. normalize + dedup against registry_edges    (fuzzy match, LLM tiebreak)
  4. FAN OUT: gather(S1-Q2 verify(c) for c in new[:6])   ← unbounded at plan time, capped for budget
  5. registry.upsert(verified | announced_only)
  6. in parallel with 4: S1-B1, S1-B2, S1-Q3..Q6
  7. emit CMI inputs {formation, destruction, intensity}
Stage2Agent: same shape, S2-Q1 → S2-Q2 counterparty verification fan-out
```

Step 4 is what a reviewer should watch in the trace: one scan probe expanding into six parallel verifications.

---

## 5. Prompts

### 5.1 `extract()` — shared Pattern B system prompt

```
You extract structured facts from a finance research report.
Rules:
- Use ONLY facts present in the provided text. Never infer or add outside knowledge.
- Copy the [[n]] citation marker that appears with each fact into the citation field.
- If a field is not stated, output null. Never guess a number or date.
- Output JSON matching the schema exactly. No prose.
```
User message = Finance Research markdown + `sources[]` + target schema. Only failed regex blocks are sent (usually 0–2 per call).

### 5.2 FINDING template (appended to every Finance Research `input`)

```
Answer using this exact structure. One block per finding:

### FINDING
- COMPANY: <name>
- EVENT: <one of: {ENUM}>
- DATE: <YYYY-MM-DD or "unknown">
- VALUE: <number + unit, or "n/a">
- QUOTE: "<exact sentence from the source>"
- CITATION: <[[n]] marker>

If nothing found, output one block with EVENT: none_found. No prose outside blocks.
```
`{ENUM}` is injected per call site from the event-type config. Labeled fields parse by regex first; Haiku is the fallback, not the primary.

### 5.3 F1 rhetoric scorer (local, temperature 0)

```
Score this Federal Reserve speech on hawkishness, -1.0 to +1.0.
Anchors:
 +1.0  explicit signal of further tightening; inflation framed as primary risk
 +0.5  concern about inflation persistence, no commitment
  0.0  balanced risks, data-dependent, no directional lean
 -0.5  concern about labor market softening or growth
 -1.0  explicit signal of easing

Output JSON: {"score": float, "evidence_quote": "<one sentence justifying the score>"}
Score the language used, not your view of policy. Ignore boilerplate.
```
Factor value = mean(last 5 speeches) − mean(prior 5).

### 5.4 F2 guidance tone (local, over extracted QUOTE fields)

```
Score management's guidance confidence 0-10.
 9-10 raised guidance with specific numeric targets
 7-8  maintained with confident, specific language
 5-6  maintained with vague or qualified language
 3-4  hedged, wide ranges, deferred specifics
 0-2  lowered or withdrew guidance

Output JSON: {"score": int, "hedging_phrases": [str], "quote": str}
```

Upstream Finance Research input, per ticker:
```
For <TICKER>'s most recent earnings call and quarterly filing: management's forward
guidance, whether guidance was raised/maintained/lowered/withdrawn, the specific
forward-looking language used about demand, and any hedging or qualifying language.
[FINDING template]
```

### 5.5 F6 hype classifier (batched, 10 articles/call)

```
For each article, identify bubble-narrative markers:
 new_paradigm | this_time_different | infinite_demand |
 profitless_growth_celebrated | price_target_leapfrog | fomo_framing

Mark a marker present ONLY if the article asserts it, not if it quotes someone
skeptically or reports that others believe it.

Output JSON: [{"url": str, "markers": [str], "quote": str|null}]
```
The skeptic-exclusion clause is load-bearing: coverage *about* bubble fears must not register as hype.

### 5.6 F3 edge entity extraction (S1-Q1 / S2-Q1)

```
From these articles, extract announced financing or investment relationships.
For each: investor/vendor, recipient/customer, dollar amount if stated, announcement
date, and whether the article states the recipient is also a customer of the investor.
Only include relationships explicitly stated in the text. Output JSON array; use null
for anything not stated.
```

### 5.7 Binary signal questions (Pattern A schema)

Schema and question list: HANDOVER §4 and battery §6–7. The model returns `signal_strength`, but **config re-maps `event_type → strength` deterministically** — the LLM label is advisory only.

---

## 6. Persistence (Postgres)

```sql
CREATE TABLE runs(
  run_id        TEXT PRIMARY KEY,
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at   TIMESTAMPTZ,
  status        TEXT NOT NULL,              -- running | done | failed
  total_cost    NUMERIC(10,4) DEFAULT 0,
  bti           NUMERIC(5,2),
  prev_bti      NUMERIC(5,2));

CREATE TABLE run_events(
  id             BIGSERIAL PRIMARY KEY,     -- monotonic cursor for GET /events?since=
  run_id         TEXT REFERENCES runs(run_id) ON DELETE CASCADE,
  ts             TIMESTAMPTZ NOT NULL DEFAULT now(),
  factor         TEXT, probe_id TEXT, event_type TEXT,
  endpoint       TEXT, params_summary TEXT,
  cost           NUMERIC(10,4), elapsed_ms INTEGER,
  cache_hit      BOOLEAN DEFAULT false,
  detail         JSONB);
CREATE INDEX ON run_events(run_id, id);

CREATE TABLE evidence(
  evidence_id  TEXT PRIMARY KEY,
  run_id       TEXT REFERENCES runs(run_id) ON DELETE CASCADE,
  factor       TEXT NOT NULL, probe_id TEXT, window TEXT,
  metric       TEXT NOT NULL, value NUMERIC, unit TEXT, as_of DATE,
  quote        TEXT, source_url TEXT,
  confidence   TEXT CHECK (confidence IN ('high','medium','low')),
  provenance   JSONB);
CREATE INDEX ON evidence(run_id, factor);
CREATE INDEX ON evidence USING GIN (provenance);

CREATE TABLE factor_results(
  run_id      TEXT REFERENCES runs(run_id) ON DELETE CASCADE,
  factor      TEXT, sub_metrics JSONB, score NUMERIC(5,2),
  state       TEXT CHECK (state IN ('ok','stale','low_coverage','failed')),
  cost        NUMERIC(10,4),
  PRIMARY KEY(run_id, factor));

CREATE TABLE signatures(
  run_id       TEXT REFERENCES runs(run_id) ON DELETE CASCADE,
  signature_id TEXT, lamp TEXT CHECK (lamp IN ('fired','partial','watch','not','no_data')),
  strong_count INTEGER DEFAULT 0, weak_count INTEGER DEFAULT 0,
  driving_evidence_ids TEXT[],
  PRIMARY KEY(run_id, signature_id));

CREATE TABLE registry_edges(
  edge_id      TEXT PRIMARY KEY,
  from_entity  TEXT, to_entity TEXT, archetype TEXT,
  amount_usd_m NUMERIC, announced_date DATE,
  status       TEXT CHECK (status IN ('verified','announced_only','contradicted','unverified')),
  seed_source_url TEXT, last_verified_run TEXT,
  UNIQUE(from_entity, to_entity, archetype));   -- dedup guard for scanner upserts

CREATE TABLE probe_cache(
  probe_id   TEXT, window TEXT,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  payload    JSONB,
  PRIMARY KEY(probe_id, window));
```

**What Postgres buys us over SQLite:**
- **Concurrent writers** — each agent writes its own evidence rows directly; no single-writer rule, no write queue back to the orchestrator.
- **JSONB + GIN** — provenance and sub-metrics are queryable, so the eval panel and cost breakdowns are one query each.
- **`ON CONFLICT` upserts** — `registry_edges` dedup and `probe_cache` writes become atomic one-liners (the scanner fan-out relies on this).
- **`TEXT[]`** for `driving_evidence_ids` — no JSON round-trip in the signature engine.

**Rules unchanged:** rows commit as each probe lands, so the DB *is* the event log — no streaming layer. Every run is fully replayable (`GET /state?run_id=`), which doubles as the demo fallback.

**Ops notes:**
- `asyncpg` with a **small pool (5–10)** — free/starter Postgres tiers cap connections tightly; an unbounded pool plus 6 concurrent agents will exhaust it.
- Wrap each probe write in its own short transaction. Never hold a transaction open across a You.com call.
- Render free Postgres instances are time-limited (~30 days) — fine for the hackathon, but keep DDL in `schema.sql` so the DB is recreatable in one command if it disappears.
- Keep `DATABASE_URL` in env; local dev via `docker run postgres:16`. No SQLite fallback path — one target, no dual-dialect bugs.
- Optional (skip unless free): `LISTEN/NOTIFY` could push run updates instead of polling. Polling stays the default — it is simpler and already spec'd.

---

## 7. API contract (polling, no SSE)

| Endpoint | Returns |
|---|---|
| `GET /state` | current scores, factor states, 12 signature lamps with `strong_count`/`weak_count`, `run_id`, `status`, `updated_at` |
| `GET /state?run_id=X` | same shape for any past run (replay / demo fallback) |
| `GET /events?since=<id>` | `run_events` rows after cursor — powers the live trace view |
| `GET /evidence/{factor}` | evidence rows + provenance for the drawer |
| `POST /rescore` | admin key; starts a run, returns `run_id`; 409 if one is active |

Frontend polls `/state` every 2 s while `status=running`, 15 s when idle; keeps last `event.id` as cursor for `/events`. Score-change choreography is a client-side diff of consecutive `/state` payloads.

---

## 8. Reliability rules

| Situation | Behavior |
|---|---|
| Probe fails / times out | factor keeps last-good score, state `stale`, failure row in trace. Never blanks. |
| Two probes disagree on one metric | both stored, metric excluded from score, `⚠ conflicting sources` in UI. Never silently averaged. |
| Budget pressure at preflight | drop priority-3 probes, mark factors `low_coverage` |
| Extraction fails validation | retry once with error appended; still failing → `confidence=low`, excluded from score, visible in trace |
| Cache hit | evidence reused, `cache_hit=1` emitted (honest, and cheap) |
| Concurrent rescore | 409; one run at a time via `asyncio.Lock` |

---

## 9. Eval harness (`/eval`)

Run 3× back-to-back, then:
- **Score variance** per factor — `SELECT factor, AVG(score), MAX(score)-MIN(score) FROM factor_results GROUP BY factor`. Target σ < 5 points.
- **Citation validity** — sample 10 `source_url`s; assert HTTP 200 and that the claimed figure appears in fetched text.
- **Extract-chain failure rate** — % of FINDING blocks needing Haiku fallback, % failing validation after retry.
- **Cost accounting** — `SELECT factor, SUM(cost) FROM run_events GROUP BY factor`.

All four are single queries against the same DB. Results table lives at the bottom of this file after the first eval run.
