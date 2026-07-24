# HANDOVER.md — Bubble or Not (You.com Agentic Hackathon) — v2 FINAL

Self-contained brief for Claude Code. All decisions final. Companion docs (same folder): `bubble-monitor-methodology.md` (factor formulas; F3 section superseded by battery doc), `f3-circularity-query-battery.md` (v2 — F3 queries + signal taxonomy), `bubble-monitor-data-sourcing.md`, `bubble-monitor-screen1-ui-spec.md`, `bubble-monitor-architecture.mermaid`, `agents-README.md` (probe registry, prompts, DDL, API contract).

---

## 1. Event context & strategy

**Event:** You.com Agentic Hackathon @ AWS Builder Loft, SF. One-day build, live 3-min demos.
**Track:** Real-Time Intelligence (only track naming finance; least fakeable). Mention Deep Research + Multi-Agent as architecture in the pitch.
**Judges (all engineers):** Rajani Thakur (Eng Lead, Microsoft) · Rutansh Trivedi (Sr Staff SWE, Palo Alto Networks) · Kruti Tailor (Sr AI Engineer, You.com — will inspect API usage depth) · Sandeep Salwan (SWE, Amazon).
**Rubric (prior You.com hackathon; confirm at kickoff):** Innovation 25% · Technical 25% · Impact 20% · UX 15% · Presentation/Docs 15%. Prior winners: real pain + citations + polished one-page UI.
**Prizes:** 1st ≈ $1k Amazon + $1k You.com credits + partner credits. **Special: $500 best use of Opsera Forge** — scaffold something through it, keep the work-order screenshot.
**Partner tools used:** Replit Agent (frontend), Render (backend + cron + static). You.com's Finance Research API is newly launched — making it shine is the political win.

**One-liner:** *"Bubble or Not — a multi-agent evidence engine that prosecutes the 'is AI the new dot-com' question live, with citations."*
**Demo shape:** live headline → verdict screen → evidence trace (typed objects + citations) → eval slide → stage sentence close. Live rescore on stage with visible agent trace.
**Pitch lines to keep:** "LLMs gather evidence; scores are computed, not generated." · "One CFO sentence outweighs five analyst notes — our aggregation encodes that." · "We compute the floor, not the truth; here's every source." · "Agentic where research beats a data feed; a data feed where it beats research."

---

## 2. Verified You.com API surface

**Core fact: no structured finance endpoints.** Everything returns search results, page content, or agentic research (cited prose / schema'd JSON). You.com = discovery + extraction; hard numbers = FMP/yfinance.

| Endpoint | URL | Auth | Key params / notes |
|---|---|---|---|
| Web Search | `GET https://ydc-index.io/v1/search` | `X-API-Key` | `query`, `count` 1–100, **`freshness`** = `day`/`week`/`month`/`year`/`YYYY-MM-DDtoYYYY-MM-DD` (server-side index filter — primary recency control), `include_domains`/`exclude_domains` (together → 422), `boost_domains`, `livecrawl` `web`/`news`/`all` (+$1/1k pages), `livecrawl_formats:["markdown"]`, `country`, `offset`. Returns `results.web[]`, `results.news[]` each w/ `url,title,snippets,page_age`. |
| Contents | `POST https://ydc-index.io/v1/contents` | `X-API-Key` | `urls[]`, `formats:["markdown","metadata"]`, `max_age` (cache), `crawl_timeout`. |
| Research | `POST https://api.you.com/v1/research` | `X-API-Key` | `input` ≤40k, `research_effort` `lite`/`standard`/`deep`/`exhaustive`, **`source_control`** `{include_domains[],exclude_domains[],boost_domains[],freshness,country}` (include+exclude exclusive; include+boost exclusive), **`output_schema`** (typed JSON; banned with `lite` → 422). Returns `output.content` (md `[[n]]` cites or JSON), `output.content_type`, `output.sources[]`. |
| Finance Research | `POST https://api.you.com/v1/finance_research` | `X-API-Key` | `input` ≤40k, effort **`deep`/`exhaustive` only. NO schema, NO source_control, NO freshness.** Best index: filings/transcripts/estimates (S&P-grade). Same output shape as Research. |
| Account Balance | billing endpoint (docs → Billing) | `X-API-Key` | poll during build; show live on Screen 2. |
| Live News | `livenews` | — | **❌ early-access only. Do not use.** Search `news` + freshness covers it. |
| Agents runs | `/v1/agents/runs` | Bearer | **Avoid** — black-box; we need our own visible orchestration. |
| MCP | `https://api.you.com/mcp` | key | dev-time experimentation in Claude Code (`?profile=free` keyless, 100/day). |

**Pricing/1k:** Search $5 (+livecrawl $1/1k pages) · Contents ~$1 · Research lite $12 / standard $50 / deep $100 / exhaustive $450 · Finance Research deep ~$110 tier. **$100 free credits** (+hackathon perk credits). Full rescore (5-name universe) ≈ $3–4. Rules: 5-ticker universe, cache via `max_age`, `standard` where possible, mock during UI dev, poll balance.

**`output_schema` rules (Research only):** root object; every object `properties`+`additionalProperties:false`; **every property in `required`**; optionals = nullable `["number","null"]`; no `allOf/if/pattern/format/min*/max*/uniqueItems`; conditionals = discriminated `anyOf` under a property; depth ≤5, ≤100 props. Non-nullable strings return `""` when unknown → make unknowns nullable.

### Recency layering (for all delta queries)
1. `freshness` param (or `source_control.freshness`) — does ~95%; **explicit ranges `YYYY-MM-DDtoYYYY-MM-DD` preferred** for reproducible non-overlapping windows
2. Client-side `page_age` filter on results
3. Extracted event-date check vs window (a fresh article about an old deal must not count as formation)
Query text describes *content only*, never time — the index ignores prose dating.

---

## 3. Extraction patterns (final)

**Pattern A — typed, domain-locked (Research API):** `output_schema` + `source_control`. Use for: F1 rhetoric (federalreserve.gov), F3 counterparty filings (sec.gov), **all binary signal questions**.

**Pattern B — Finance Research → structured-markdown → extract chain.** For anything needing the finance index (F2 estimates/transcripts/tone, F4 insider, S2-Q6 aggregates). Rationale: Finance Research answers from the *right documents*; structure is recovered client-side. Append this template to every Finance Research call:

```
Answer using this exact structure. One block per finding:

### FINDING
- COMPANY: <name>
- EVENT: <one of: guidance_cut | guidance_withdrawn | reported_miss | analyst_estimate_cut | impairment | order_cancellation | none_found>
- DATE: <YYYY-MM-DD or "unknown">
- VALUE: <number + unit, or "n/a">
- QUOTE: "<exact sentence from the source>"
- CITATION: <[[n]] marker>

If nothing found, output one block with EVENT: none_found. No prose outside blocks.
```
(Adapt EVENT enum per call site from the event-type config.)

**Chain:** regex split `### FINDING` → field parse → Haiku (Anthropic API) only for failed blocks, context = the FR output only, instruction "only facts present in text, carry [[n]] markers" → Pydantic validate (retry once w/ error appended; still failing → confidence=low, excluded from score, visible in trace) → map `[[n]]`→`sources[n].url` → evidence objects. **Write once as `extract(markdown, sources, schema) -> list[Evidence]`; every Pattern B call site shares it; eval harness reports its failure rate.** Log raw md + parsed objects in trace. `none_found` = typed empty answer (countable, unambiguous).

**Decision rule per call site:** structure-critical + open-web-answerable → Pattern A. Finance-index-critical → Pattern B. Pure numbers → FMP/yfinance, no LLM.

---

## 4. Signal taxonomy & aggregation (applies to ALL factors)

**Strong = company speaking against its own interest:** guidance cut/withdrawn, reported miss vs own guidance, impairment, covenant disclosure, canceled order, auditor change. Near-zero false positives.
**Weak = third-party opinion / noisy proxy:** analyst estimate cuts, price targets, GPU spot drift, "people familiar" reports, short theses.
Timing: weak moves first, strong confirms. Expected cracking sequence = weak cluster → strong confirmation.

**Deterministic aggregation per signature:**
```
strong_count >= 1                       -> FIRED (red)
weak_count >= K in window (K~3, config) -> PARTIAL (yellow, "cluster forming")
weak_count 1..K-1                       -> WATCH (gray, count shown)
```
UI: each signature row shows counters `S:1 W:4`. Event→strength mapping lives in **config**, not the LLM — the model only extracts events; classification is ours.

**Binary-question pattern (Pattern A, `standard` effort, freshness-windowed):** one yes/no question per signal type, schema:
```json
{"type":"object","properties":{
  "answer":{"type":"boolean"},
  "events":{"type":"array","items":{"type":"object","properties":{
    "company":{"type":"string"},
    "event_type":{"type":"string","enum":["guidance_cut","guidance_withdrawn","reported_miss","analyst_estimate_cut","impairment","order_cancellation","covenant_issue"]},
    "signal_strength":{"type":"string","enum":["strong","weak"]},
    "date":{"type":["string","null"]},
    "magnitude":{"type":["string","null"]},
    "quote":{"type":"string"},
    "source_url":{"type":"string"}},
    "required":["company","event_type","signal_strength","date","magnitude","quote","source_url"],
    "additionalProperties":false}}},
 "required":["answer","events"],"additionalProperties":false}
```
Core strong questions: "In the last 30 days, has any publicly traded neocloud (CoreWeave, Nebius, ...) lowered or withdrawn its own revenue/cashflow/capex guidance?" · "Has NVIDIA lowered guidance or softened forward demand language in official communications, last 90 days?" · "Has any neocloud reported revenue/OCF below its own prior guidance, last 90 days?"
Core weak questions: analyst cuts / PT reductions for the neocloud complex, last 30 days · reports of compute contracts renegotiated/downsized/delayed, last 30 days.

---

## 5. Data constraints

Allowed: **You.com, FMP, yfinance** (both network-permitted here). Unavailable elsewhere → signature = `no-data`, hatched lamp, honest tooltip. Never fabricate.
**Signature-checklist pivot:** continuous 1999 overlays mostly impossible (no point-in-time IBES, no pre-Reg-FD transcripts, no electronic Form 4 pre-2003, RSP 2003+, EDGAR FTS 2001+). Per factor: research the 1999 signature once via You.com (cited prose, stored in config) + score today's data vs deterministic thresholds. True overlays that survive: **price** and **rates** (both eras, yfinance/FMP). Available 1999: daily prices, fed funds + hike dates, Fed speeches (federalreserve.gov archive), NYSE A/D + highs/lows, top-10 weight (documented).

---

## 6. Factors & methodology (final)

**Design law: LLMs gather evidence; scores are computed.** Evidence object: `{factor, metric, value, unit, as_of, source_url, quote, confidence, provenance}`.

- **F1 Liquidity (25%)** — implied path/steepness (FMP-derived), time-to-tightening, Fed rhetoric delta (Search federalreserve.gov + livecrawl → our rubric), real-rate proxy.
- **F2 Bellwethers (20%)** — universe: NVDA MSFT META GOOGL AVGO AMZN ORCL + 1 neocloud (hardcoded). Revision direction + growth delta + guidance tone (Pattern B), GPU spot 30d (Search+Contents), miss tracker (display only). Binary signal questions per §4.
- **F3 Circularity (20%)** — **archetype + registry model, two-stage CMI. Full spec: `f3-circularity-query-battery.md`.** Summary:
  - Archetypes: A equity-for-revenue (NVDA→neocloud) · B offtake/backstop · C compute-for-equity triangle · D GPU-collateralized debt · E SPV/JV datacenters · **F lab→startup revenue recycling** (credits = usage inflation not GAAP revenue; investment-funded spend = real recycled revenue; distinguish!)
  - Known-deal registry (~10–15 press-covered edges, seeded tonight). Agents **verify & size edges** (EdgeVerifier: press + counterparty sec.gov filings — attribution lives on the *counterparty* side: supplier concentration %, purchase commitments, GPU-collateral debt), never discover from vendor filings (vendors disclose aggregates without attribution).
  - Edge states: verified (scored) / announced-only (dimmed, unscored) / contradicted.
  - **Two-stage CMI:** Stage 1 usage-layer (weekly; breaks first — canary = startup churn S1-Q4) vs Stage 2 GPU-layer (monthly; breaks second — avalanche = S2-Q5 distress). CMI = formation − destruction + intensity per window; deltas from identical windowed re-runs. Composite signature: Stage-1 CMI negative while Stage-2 positive = pre-break pattern.
  - **Archetype F exhibit — Revenue Quality Waterfall** per lab (OpenAI | Anthropic, identical methodology): Reported ARR − portfolio-customer revenue (verified lower bound) − credit-cohort usage inflation − committed-vs-recognized gap = cash-quality band with whiskers; Revenue Quality Score = band midpoint / reported ARR. All press-derived, every bar cited. 1999 precedent: barter/ad-swap revenue + Lucent vendor financing.
  - F3 sub-score: Circularity Ratio (verified circular $ / total assets; tiers <1% / 1–3% ≈1999 / >3%) 50% · CMI_stage2 25% · CMI_stage1 25%.
- **F4 Insiders (15%)** — narrative + mega-sale count (Pattern B / Search), lockup dates; precise aggregates unavailable → confidence=medium, flagged.
- **F5 Breadth (20%)** — **pure quant, zero LLM:** top-10 weight, SPY−RSP 6m, %>200dma, ^TNX. FMP/yfinance.
- **F6 Narrative temp (0%, display)** — Search freshness=week + livecrawl ~50 articles → hype-marker density vs cited 1999 baseline.

**BTI** = .25·F1+.20·F2+.20·F3+.15·F4+.20·F5. ~12 signatures: {name, deterministic threshold, strong/weak aggregation per §4, 1999 precedent + citation, stage tag early/mid/late}. Stage sentence = template over fired stage-buckets. F3 signatures: usage-layer churn accelerating (early) · revenue-definition drift at labs (mid) · capex-layer edge distress (late) · vendor-financed revenue material (fires on RQ/CR thresholds).
**Eval harness:** 3× runs per agent → variance table (target σ<5) + citation-validity spot-check (N=10) + extract-chain failure rate. One slide + `/agents` README.
**Stretch only:** analog matching, 2007 backtest.

---

## 7. Architecture — 2 deployables + 1 cron

```
Static SPA (public; cached JSON only; can NEVER trigger agents)
   | polls GET /state (2s running / 15s idle) + GET /events?since=<id>
FastAPI (Render): GET /state[?run_id] · GET /events?since · GET /evidence/:factor · POST /rescore (X-Admin-Key)
   | asyncio task (Lock; concurrent -> 409)
Pipeline (in-process): orchestrator fans out F1..F6 concurrently; per-agent try/except+timeout -> stale-not-blank
   ├→ You.com (Search/Contents/Research/FinanceResearch)
   ├→ FMP + yfinance
   └→ Postgres: evidence · scores · signature states · registry edges · run_events · 1999 config
Render Cron 6h → POST /rescore   (F3 Stage-1 battery weekly, Stage-2 monthly — cadence config per query)
```
No queue/Redis/Celery. **No SSE — pipeline writes to Postgres as it goes; frontend polls `GET /state` (2s while running, 15s idle) and `GET /events?since=<id>` for the trace cursor.** Postgres (Render-provided): concurrent agent writes, JSONB provenance, `ON CONFLICT` upserts for registry dedup; asyncpg pool 5–10 (free tiers cap connections); DDL in `schema.sql`, recreatable in one command. Every run replayable via `GET /state?run_id=` — the demo fallback. `schema.py` at root = the contract. Monorepo: `/agents` (deeply documented — the artifact the You.com judge reads) · `/dashboard` · `/data/benchmarks` · `/data/registry` · `/eval`.
`run_events` rows (BIGSERIAL cursor): `run.started`, `agent.started`, `agent.tool_call{endpoint,params_summary,cost,elapsed,cache_hit}`, `agent.evidence{count}`, `agent.completed{score,state}`, `agent.failed{reason}`, `run.completed{bti,changed_signatures[]}`.

---

## 8. UI — Screen 1 (full spec in screen1 doc)

Dark single page ~1200px: **A** verdict header (BTI half-donut · "7/12 fired" dot-fuse · templated stage sentence) → **B** hero dual-timeline (1996-2001 amber vs 2023-now bright, indexed; signature pins both eras, ghost pins = unfired; toggle Price|Rates) → **C** signature board (5 groups, ~12 rows: lamp + `S:n W:n` counters + 1999 precedent chip + current reading chip + confidence; click → evidence drawer w/ typed objects, quotes, provenance line) → **D** radar (today vs dashed danger thresholds, breach fills red) + F6 thermometer ("coincident — display only") → **E** quant strip ("no LLM in this row") → **F** footer/disclaimer. **F3 extras:** two-line CMI sparkline (stage 1 weekly / stage 2 monthly) in its group header + Revenue Quality Waterfall exhibit in its drawer. Grammar: amber=1999, bright=now, red=fired, hatched=no-data; source chip on every number; motion only on rescore; A+B self-explain at 1200×630 (OG image). Recharts + bespoke SVG (gauge/thermometer). Screen 2 "Engine" (DAG, trace feed, evidence explorer, eval panel, live credit balance) built after Screen 1.

---

## 9. Build order

**Tonight:**
1. Keys (You.com, FMP) as env vars; verify Pattern A end-to-end with counterparty query: *"From CoreWeave's most recent 10-K/S-1 on sec.gov: % of supply from NVIDIA, purchase commitments to NVIDIA, customer concentration, GPU-collateralized debt — quote exact sentences + filing URLs."* Then same text through Finance Research for comparison.
2. Buy domain; scaffold monorepo + `schema.py` + fixtures (`scores.json`, `evidence.json`).
3. Seed **registry** (~10–15 edges: NVDA↔neocloud complex, hyperscaler↔lab pairs, SPVs, lab→startup fund deals) via You.com; hardcode with citations.
4. Research + hardcode 12 signature configs (precedent text, citations, thresholds, strong/weak K, stage tags).
5. **Cold-start battery:** run every F3 query once with wide windows (S1 month / S2 year) → window-0 baselines. No baseline = no delta on demo day.
6. Pull 1996-2001 price/rate series (yfinance) → `/data/benchmarks`.
7. **Config-as-code**: put weights, thresholds, prompts, registry in `/config/*.yaml`; add `config_version` (git SHA of `/config`) column to `runs`. Enables the Forge audit story (§10).

**Day:** FastAPI+Postgres+polling endpoints (1h) → F5 (fast real-data win) → F3 (showcase: EdgeVerifier + binary battery + CMI) → F1+F6 → F2+F4 → scorer/signature engine → UI vs fixtures in parallel on Replit (C → A → B → E → D) → poll-diff choreography → eval 3× runs → **last 2h locked: pitch rehearsal ×2, README + architecture diagram, 60s backup recording, OG screenshot.**
**Cut line:** F1/F3/F5/F6 + 8 signatures; F2/F4 as no-data (UI handles honestly by design).

---

## 10. Sponsor tooling — build vs adopt

**Adopt:** Render Cron (scheduler; at-most-one-run-active matches our lock; $1/mo min, 12h cap) · Render Postgres (assume provided by sponsors) · Replit Agent (**UI only** — live preview is what chart polish needs) · Opsera Forge (**backend scaffold + audit**, see below).
**Reject:** MindStudio (could run our orchestration — scheduled agents, webhooks, JS/Python blocks, 200+ models at cost — but it's a visual black box; the DAG fan-out and trace ARE the Technical Implementation evidence. Catastrophe fallback only) · You.com Agents API · CrewAI (same reason).
**Deploy gotcha:** a Render *free* web service cannot attach a persistent disk and spins down after 15 min idle. Use a paid instance or Render Postgres — do not discover this on demo day.

**Opsera Forge play ($500 special prize), time-boxed to 45 min:**
- Backend scaffold via spec → our docs (this file, `schema.sql`, API contract) are already machine-readable specs written before any code — the literal Forge use case.
- **Audit story (the strong version):** Forge work orders gate changes to `/config` (weights, thresholds, prompts). `runs.config_version` joins a score back to the work order that approved the rubric it used. Forge owns *why the rubric is what it is*; Postgres owns *what it produced*. Pre-empts the standing critique of any index ("you tuned weights until you liked the answer").
- Runtime agent runs are NOT in Forge's scope — that's our `run_events`/`evidence` tables.
- Capture for submission: work-order audit trail, ForgeScore output, one slide showing spec → generated code.
- Pitch rhyme: *ForgeScore is an 8-dimension evidence scorecard for code; BTI is a 5-factor evidence scorecard for markets.*
- **Verify at their booth:** can work orders wrap changes to an existing repo (not just new generation), and do they expose IDs referenceable from commit messages? If setup exceeds 45 min, fall back to Claude Code for backend and use Forge on a smaller artifact (schema module or eval harness) — still a legitimate submission.
- Not chosen for UI: spec-driven generation can't do "make the amber dimmer"; governance friction compounds across ~30 UI revisions.

---

**Close:** "We don't say bubble. We show you where 1999's fingerprints match — with a citation on every claim."
