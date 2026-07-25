# /agents — Multi-Agent Evidence Engine

How Bubble or Not gathers evidence, how agents coordinate, and why the scores
are reproducible. **LLMs gather evidence; scores are computed, never generated.**

## Three intelligence layers, strictly separated

| Layer | Does | Never does |
|---|---|---|
| You.com research agents | open-ended gathering across their index | arithmetic, verdicts |
| Local LLM (Haiku, temp 0) | bounded rubric judgment: extraction, rhetoric/tone/hype scoring, entity resolution | free-form reasoning, scoring math |
| Our code | all arithmetic, thresholds, aggregation, signature lamps | anything requiring language understanding |

Consequence: identical evidence yields identical scores. A judge can recompute
any lamp by hand from the evidence table: `strong ≥ 1 → FIRED · weak ≥ K →
PARTIAL · else WATCH/NOT`. The event→strength map lives in `config/events.yaml`,
not in any model — the LLM's own strength label is stored as *advisory only*
(`provenance.llm_strength_advisory`) next to the one we used.

## Extraction patterns

- **A — typed, domain-locked** (`youcom.research` + `output_schema` +
  `source_control`): binary signal questions, counterparty filings (sec.gov),
  edge verification. Zero parsing; unknowns come back `null`, never `""`.
- **B — Finance Research → FINDING template → `extract()`** (`agents/extract.py`,
  written once, shared by every call site): regex-split → field-parse → **Haiku
  only for failed blocks** → Pydantic validation (one retry) → `[[n]]`→URL.
  Crawl-error text is rejected as a quote at validation (a live failure mode we
  hit in testing). Blocks that still fail become `confidence=low`, score-excluded,
  visible rows — never silently dropped.
- **SEARCH** — Search API (+ Contents fallback when livecrawl markdown is thin)
  → Haiku classification (hype markers, entity extraction, price extraction).
- **QUANT** — FMP/yfinance, pure math, no LLM (F5, F1 rates, CR denominator).

## Live probe registry

| Probe | Factor | Pattern | Endpoint | ~$ | Notes |
|---|---|---|---|---|---|
| F5-top10/eqw/200dma/tnx | f5 | QUANT | fmp, yfinance | 0 | deterministic, 501-name coverage |
| F1-rates | f1 | QUANT | fmp | 0 | 1Y−EFFR path proxy |
| F1-rhetoric | f1 | SEARCH | search `federalreserve.gov` + contents | 0.02 | Haiku hawkishness rubric ×10 speeches |
| F2-B1 / F2-B2 | f2 | A | research `standard` | 0.05 ea | strong/weak binaries, windowed |
| F2-tone-{T} ×4 | f2 | B | finance_research `deep` | 0.11 ea | tone rubric over extracted quotes |
| F2-gpu-spot | f2 | SEARCH | search + Haiku | 0.01 | 30d delta from OUR stored samples |
| F2-growth | f2 | B | finance_research `deep` | 0.11 | NTM vs LTM per bellwether |
| F4-insider | f4 | B | finance_research `deep` | 0.11 | mega-sales; 10b5-1 weighted 0.5× |
| F6-narrative | f6 | SEARCH | search wk + Haiku ×5 batches | 0.06 | skeptic-exclusion clause load-bearing |
| S1-B1 drift / S2-B1 strong | f3 | A | research `standard` | 0.05 ea | typed events |
| S1-Q1/S1-Q4/S2-Q1/S2-Q5 scans | f3 | SEARCH | search livecrawl=news | 0.01-0.04 | formation & destruction counts |
| **S1-Q2 verify ×≤4** | f3 | A | research `standard` | 0.05 ea | **the fan-out** — investee AND customer? |
| **S2-Q2 counterparty** | f3 | A | research `deep` + sec.gov | 0.10 | the flagship: filings quotes, typed |
| S1-Q5 ARR ×2 | f3 | SEARCH | search + Haiku | 0.01 | metric-phrase drift detector |

Full uncached run ≈ **$1.0–1.5**; typical rescore with warm caches ≈ **$0.30**.
Preflight checks the live balance and drops priority-3 probes (F4) under $5.

## F3 — the genuinely agentic factor

Registry of 12 press-cited edges (`data/registry/edges.yaml`, archetypes A–F).
Stage 1 (usage layer, weekly window) and Stage 2 (GPU layer, monthly) run
concurrently; Stage 1's scan expands into parallel verifications — watch
`run_events` for one `S1-Q1` tool_call followed by N `S1-Q2:*` calls. Edges are
scored **only after counterparty corroboration** (sec.gov filings for A/B/C,
usage evidence for F). CMI deltas compare against the cold-start window-0
baselines (`scripts/cold_start_f3.py` — mandatory before demo day).
Composite pre-break signature: Stage-1 CMI < 0 while Stage-2 > 0.

Circularity Ratio = verified circular $ / universe total assets (FMP balance
sheets). Announced-only edges render dimmed and score **zero** — we compute
the floor, not the truth.

## Orchestration & reliability

`POST /rescore` (admin key) → asyncio.Lock (concurrent → 409) → preflight
(balance, priority drop) → gather(F1..F6) with per-agent `asyncio.wait_for`
timeouts → deterministic reduce → BTI. Every probe writes `run_events` +
`evidence` rows as it lands — **the DB is the event log**; every run replays
via `GET /state?run_id=` (the demo fallback).

| Situation | Behavior |
|---|---|
| Probe fails / times out | factor keeps last-good score, state `stale`, reason in trace |
| Metric not derivable from allowed sources | hatched `no_data` row + honest tooltip |
| Conflicting evidence on one metric | both stored, excluded from score, ⚠ banner |
| Budget pressure | priority-3 dropped at preflight, factor `low_coverage` |
| Cache hit (TTL per probe) | `cache_hit=true` in trace, $0 |

Endpoint semaphores: search 5 · research 3 · finance_research 4. Costs and the
account balance are logged in `run.started`/`run.completed` events.

## API contract

| Endpoint | Returns |
|---|---|
| `GET /state[?run_id]` | full dashboard payload (scores, 12 lamps + S/W counters, hero series, F3 exhibit) |
| `GET /events?since=<id>` | trace rows after cursor |
| `GET /evidence/{factor}` | typed evidence + provenance |
| `POST /rescore` | `X-Admin-Key`; 202 or 409 |

## Eval

`eval/run_eval.py` → variance table (target σ<5), citation-validity sample,
extract-chain failure rate, cost per factor. Results: `eval/RESULTS.md`.
Known outlier: F4 swings across uncached runs because Finance Research
surfaces different insider findings per pull — caching stabilizes within a
day and the variance is visible, not hidden.
