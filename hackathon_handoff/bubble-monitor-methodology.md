# Bubble Monitor — Factor Calculation Methodology v1

> **⚠️ SUPERSEDED IN PART (see HANDOVER.md).** Three changes since this was written:
> 1. **FRED/CME unavailable** — allowed sources are **You.com, FMP, yfinance only**. Substitute FMP/yfinance or mark `no-data`.
> 2. **Factor 3 is fully superseded** by `f3-circularity-query-battery.md` (archetypes A–F, known-deal registry, two-stage CMI, signal taxonomy).
> 3. **Signal taxonomy added** — all factors now use strong/weak classification with the aggregation rule in HANDOVER §4 (strong ≥1 → FIRED; weak ≥K → PARTIAL).
> 4. **1999 continuous benchmarks are mostly unobtainable** — the "signature checklist" pivot replaces them (cited 1999 signature + today's reading vs deterministic threshold). Only price and rates survive as true then-vs-now overlays.
>
> Formulas, normalization bounds, and edge cases for F1, F2, F4, F5, F6 remain accurate.


**Goal:** Six dimensions, each computed from typed evidence → deterministic 0–100 score → compared against digitized 1997–2001 monthly benchmarks → historical analog matching ("the 1999 clock").

**Design rule:** LLM agents *gather and extract* evidence. Scores are *computed*, never generated. Every evidence object carries `{metric, value, unit, as_of, source_url, confidence}`.

---

## Factor 1 — Liquidity Withdrawal (weight 25%)

**Thesis:** Bubbles die of tightening. Forward-looking via market-implied rate path, not realized hikes.

### Sub-metrics
| Metric | Calculation | Data source |
|---|---|---|
| Implied hike probability | P(hike) at next 2 FOMC meetings from Fed Funds futures | CME FedWatch (agent scrapes via Search API), or futures prices → P = (implied rate − current EFFR) / 25bp |
| Path steepness | Implied rate 12m out − current EFFR (bp) | Fed funds futures curve / SOFR futures |
| Time-to-tightening | Days until first meeting with P(hike) > 50% | Derived from above |
| Fed rhetoric shift | Hawkishness delta of last 5 Fed speeches vs prior 5 (LLM-scored −1 to +1 per speech, rubric-anchored) | Research API on Fed communications |
| Real rate level | 10Y TIPS yield | FRED (DFII10) |

### Score
```
liquidity_score = 100 × (0.30·norm(path_steepness, 0bp, +200bp)
                       + 0.25·norm(P_hike_next2, 0, 1)
                       + 0.20·norm(rhetoric_delta, −1, +1)
                       + 0.15·(1 − norm(time_to_tightening, 0d, 365d))
                       + 0.10·norm(real_rate, 0%, 3%))
```
Higher = more withdrawal pressure = closer to pin.

### 1999 benchmark anchors (hardcode tonight)
Jun-99: first hike, path pricing +100bp/12m. Feb-00: path +125bp, rhetoric fully hawkish → score ≈ 85. Digitize monthly from FRED (FEDFUNDS) + Fed meeting history.

### Edge cases
- Futures data unavailable → fall back to latest FedWatch snapshot cached at cron time; flag `stale=true` in UI.
- Cutting cycle (negative steepness) → score floors at 5, label "liquidity tailwind."

---

## Factor 2 — Bellwether Earnings Quality (weight 20%)

**Thesis:** Two lenses — (a) forward: is expected growth *decelerating*? (b) leading physical proxy: GPU/compute spot prices as demand telemetry for the neocloud complex.

### Universe
Fixed list of 8 bellwethers: NVDA, MSFT, META, GOOGL, AVGO, AMZN, ORCL, + 1 neocloud (CRWV or similar). Hardcoded; agent enriches each.

### Sub-metrics
| Metric | Calculation | Data source |
|---|---|---|
| Estimate revision momentum | For each bellwether: (current NTM EPS consensus − consensus 90d ago) / 90d-ago consensus. Portfolio metric = median | Finance Research API (analyst estimates); fallback: agent extracts from recent coverage |
| Growth deceleration | NTM expected revenue growth − LTM realized growth (negative = deceleration) | Finance Research API |
| GPU price proxy | Spot H100/B200 rental $/GPU-hr, 30d change | Search API on GPU pricing indexes/marketplaces |
| Guidance tone | LLM rubric score of latest earnings-call guidance language per bellwether: confidence 0–10 (anchored: "raise + specific numbers"=9, "maintain"=5, hedged/withdrawn=2). Median across universe | Research API on call transcripts |
| Miss tracker (lagging, displayed not scored) | Count of misses last quarter across universe | Finance Research API |

### Score
```
bellwether_score = 100 × (0.35·(1 − norm(revision_momentum, −10%, +10%))
                        + 0.25·(1 − norm(growth_delta, −20pp, +10pp))
                        + 0.20·(1 − norm(gpu_price_30d, −25%, +10%))
                        + 0.20·(1 − guidance_tone/10))
```
Higher = deteriorating forward earnings picture.

### 1999 anchors
Mid-99: revisions still positive, score ≈ 30. Q1-00: first deceleration in estimate revisions for CSCO/NT complex, score ≈ 60. (Digitize from historical consensus data where findable; else anchor qualitatively from contemporaneous coverage — cite it.)

### Edge cases
- Consensus data not retrievable for a name → drop from median, require ≥5 names else flag dimension `low_coverage`.
- GPU spot sources conflict >20% → agent-disagreement flag; use median of sources, surface all citations.

---

## Factor 3 — Circular / Off-Balance-Sheet Financing (weight 20%)

**Thesis:** Revenue funded by your own capital is fictional growth. Measure circularity *relative to balance sheet size* so eras are comparable.

### Circularity Ratio (the headline number)
```
CR_company = (vendor financing to customers
            + equity/debt investments in entities that are also customers
            + SPV/JV datacenter commitments not consolidated
            + purchase obligations to related counterparties)
            / total assets
```
Portfolio metric: asset-weighted mean CR across the bellwether universe + named circular pairs.

### Extraction method (the agent showcase)
Agent per company runs a research plan against Finance Research API + Search API:
1. Pull latest 10-K/10-Q footnotes: "commitments and contingencies," "variable interest entities," "related party."
2. Extract dollar values into typed evidence objects with source paragraph citation.
3. Cross-check against news coverage of announced deals (e.g., chipmaker equity stake in customer X announced with supply agreement).
4. Build a **circularity graph**: nodes = companies, edges = {investment $, purchase commitment $}. Detect cycles (A invests in B, B buys from A). Cycle edge value sum = headline "circular dollars."

### Score
```
circularity_score = 100 × norm(portfolio_CR, 0%, 8%)
Tiers displayed: <1% comparable-to-normal · 1–3% elevated (≈1999 vendor financing) · >3% exceeds 1999
```

### 1999 anchors
Lucent + Nortel + Cisco vendor financing peaked ≈ $15–25B against combined assets → CR ≈ 2–3%. Hardcode with citations from retrospective coverage (agent researches this tonight, human-verified).

### Edge cases
- Footnote value given as range → take midpoint, confidence=0.6.
- Two agents extract different figures for the same commitment → disagreement flag, show both, exclude from score until resolved. **Never average silently.**
- Non-USD → convert at as-of FX (FRED).

---

## Factor 4 — Insider Selling & Lockup Supply (weight 15%)

### Sub-metrics
| Metric | Calculation | Data source |
|---|---|---|
| Insider sell/buy ratio | Universe-wide $ sold / $ bought, trailing 90d, vs trailing 3y median | Form 4 aggregates via Finance Research API / Search API on insider-tracking coverage |
| Founder/CEO mega-sales | Count of >$100M single-insider sale programs announced, trailing 90d | News via Search API |
| Supply overhang | $ value of announced secondaries + upcoming IPO lockup expiries next 90d, as % of 30d ADV of the universe | Search API |

### Score
```
insider_score = 100 × (0.50·norm(sell_buy_ratio / 3y_median, 1×, 4×)
              + 0.30·norm(mega_sale_count, 0, 6)
              + 0.20·norm(overhang_pct_adv, 0%, 15%))
```

### 1999 anchors
Insider selling ran ≈3–4× historical norm through H2-99; early-2000 lockup wave (Nov-99 IPO cohort unlocking Mar–Apr-00) coincided with peak. Score ≈ 80 at Feb-00.

### Edge cases
- 10b5-1 scheduled sales vs discretionary: if plan disclosure found, weight 0.5×.
- Data sparsity → widen window to 180d, flag.

---

## Factor 5 — Breadth & Concentration Divergence (weight 20%)

**Fully quantitative — no LLM in the loop. This is the "we also do plain math correctly" dimension.**

### Sub-metrics
| Metric | Calculation | Data source |
|---|---|---|
| Concentration | Top-10 weight in S&P 500 | Index data via Finance Research API |
| Breadth divergence | (SPY 6m return) − (RSP equal-weight 6m return) | Price data (yfinance/FMP allowed by network config, or Finance Research API) |
| Participation | % of S&P 500 members above 200dma | Computed from constituent prices |
| New-high starvation | 52wk-highs minus 52wk-lows (NYSE), 20d avg | Market internals via Search API |

### Score
```
breadth_score = 100 × (0.30·norm(top10_weight, 25%, 42%)
              + 0.30·norm(spy_minus_rsp_6m, 0pp, 12pp)
              + 0.25·(1 − norm(pct_above_200dma, 30%, 75%))
              + 0.15·(1 − norm(hl_spread, −200, +200)))
```

### 1999 anchors
Directly computable from historical price data — the one dimension where the 1997–2001 series is fully reconstructable tonight in a notebook. Dec-99: index at highs, NYSE breadth negative since Apr-98 → score ≈ 85. **This dimension anchors the backtest slide.**

### Edge cases
None material; pure data. Missing constituent → drop, renormalize.

---

## Factor 6 — Narrative Temperature (displayed, weight 0% in trigger model)

**Coincident sentiment gauge — explicitly labeled non-predictive. Innovation showcase.**

- Agent samples last 7 days of financial media via Search API, N≈100 articles on AI/markets.
- LLM classifies each for hype-markers: "new paradigm," "this time is different," "can't lose," price-target-leapfrogging, profitless-growth celebration. Density = flagged/total.
- Benchmark: same rubric run on digitized 1999–2000 press samples (agent gathers tonight from archives/retrospectives).
- Display as thermometer beside the radar. Score = 100 × norm(density ratio vs 1999 peak, 0, 1).

---

## Composite & The 1999 Clock

### Bubble Trigger Index
```
BTI = 0.25·F1 + 0.20·F2 + 0.20·F3 + 0.15·F4 + 0.20·F5   (F6 excluded)
```

### Analog matching (the model)
- Feature vector: [F1..F5] monthly, 1997-01 → 2001-12 benchmark library (60 vectors).
- Today's vector → cosine similarity + Mahalanobis distance vs library.
- Trajectory mode: DTW over trailing 6 months of today's vectors vs all 6-month windows of 1999.
- Output: *"Closest analog: 1999-03 (similarity 0.81). In that analog, peak occurred 12 months later."*
- Confidence = similarity of best match; if <0.5 display "no strong historical analog."

### Backtest (validation slide)
- Hold-out: build 2006–2008 monthly vectors for F1, F4, F5 (data-reconstructable factors), zero-weight F2/F3.
- Show pipeline matches mid-2007 to late-stage-1999 states.
- One notebook, one chart, one sentence: "same pipeline, different bubble, correct classification."

### Eval harness
- Run each agent 3× per dimension → report score variance (target σ < 5pts) and citation-validity rate (spot-check N=10 URLs resolve + contain claimed figure).
- Publish table in /agents README.

---

## Data source summary
| Source | Used for | Access |
|---|---|---|
| You.com Finance Research API | Estimates, filings, insider data, index composition | Primary — showcase |
| You.com Search API | Fed rhetoric, GPU prices, news, media sampling, archival 1999 press | Primary — showcase |
| You.com Research API | Deep multi-hop (footnote extraction, circularity graph) | Primary — showcase |
| FRED | FEDFUNDS, DFII10, historical rates | Free, no key friction |
| Price data (FMP/yfinance) | Factor 5 + backtest | financialmodellingprep.com is network-allowed |
| CME FedWatch (scraped) | Hike probabilities | Via Search API |

## Tonight (pre-hackathon) checklist
1. Digitize 1997–2001 monthly benchmarks: F5 fully from prices; F1 from FRED + meeting history; F2–F4 anchor points from retrospective coverage with citations.
2. Run backtest notebook (F1/F4/F5, 2006–2008) → export the chart.
3. Buy domain; scaffold repo: `/agents`, `/dashboard`, `/data/benchmarks`, evidence schema file.
4. Verify You.com API access + one end-to-end evidence extraction on a single 10-K footnote.
