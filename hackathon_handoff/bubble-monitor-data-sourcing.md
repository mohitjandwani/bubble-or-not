# Bubble Monitor — Data Sourcing Map (You.com API)

> **⚠️ SUPERSEDED IN PART (see HANDOVER.md).** Two changes since this was written:
> 1. **FRED and CME are NOT available** — allowed sources are **You.com, FMP, yfinance only**. Everywhere below that names FRED (real rates, historical rate series) or CME (implied hike probabilities): use FMP economic indicators / yfinance treasury tickers instead, or mark the sub-metric `no-data`.
> 2. **Factor 3 is fully superseded** by `f3-circularity-query-battery.md` (archetype + registry + two-stage CMI model). The filing-discovery approach described below does not work — vendors disclose aggregates without attribution.
>
> The endpoint reference, availability verdicts, and cost table below remain accurate.


Companion to the methodology doc. For every sub-metric: exact You.com endpoint + how to call it, an availability verdict, and the non-You.com fallback.

---

## The one architectural fact that reshapes everything

**You.com has no structured financial-data endpoints.** There is no `GET /price?ticker=NVDA`, no estimates feed, no Form-4 feed. Everything You.com returns is one of three shapes:

1. **Search** → raw results (URL, title, snippet, `page_age`). You extract.
2. **Contents** → full HTML/Markdown of a URL you already have. You extract.
3. **Research / Finance Research** → agentic, multi-step, returns **cited prose** — or, for the general Research API only, **schema-constrained JSON**.

So "get a number from You.com" always means *agentic research returns it cited*, or *you search→read→extract it yourself*. For hard time-series numbers (prices, rates, index weights) You.com is a **discovery/extraction layer, not a source of truth** — pair it with FRED + FMP (both network-allowed).

### Verdict legend
- ✅ **Native** — agentic research returns it well (cited prose, or typed JSON via `output_schema`). You.com is the right primary source.
- ⚠️ **Extraction-only** — You.com can *find/read* it, but reliability depends on the page; you must parse. Fine for demo, caveat in docs.
- ❌ **Not a You.com capability** — no feed exists; use external. You.com can at best locate a webpage that shows the number.

### The two endpoints that matter most for you
- **Finance Research** (`POST /v1/finance_research`): best financial index — S&P Global licensed data + filings + estimates + earnings. **But no `output_schema`, no `source_control`.** Returns markdown + `[[n]]` citations + `sources[]`. Effort: `deep` (default) or `exhaustive` only.
- **Research** (`POST /v1/research`): general index, weaker on finance — **but supports `output_schema` (typed JSON) AND `source_control` (`include_domains`, `freshness`, `country`).** Effort `standard`/`deep`/`exhaustive` support schema (`lite` does not).

**Pattern A (typed):** Research API, `include_domains:["sec.gov"]` + `output_schema` → typed evidence objects, self-restricted to filings.
**Pattern B (best numbers):** Finance Research `deep` → cited prose → second cheap local LLM pass parses into your evidence schema.
Use B for anything needing S&P-grade reconciliation (estimates, fundamentals); use A for filing extraction where you want typed output and domain lock.

---

## Factor 1 — Liquidity Withdrawal

| Sub-metric | You.com method | Verdict | Fallback (source of truth) |
|---|---|---|---|
| Implied hike prob (next 2 FOMC) | Finance Research: *"market-implied probability of a Fed rate change at the next two FOMC meetings, per Fed funds futures, as of today"* → cited answer | ⚠️ cited prose, not tick-accurate | **CME FedWatch / fed funds futures** — real source |
| Path steepness (12m implied − EFFR) | Finance Research same call, ask for 12-month implied path | ⚠️ | CME futures curve |
| Time-to-tightening | Derived from the two above | n/a | — |
| **Fed rhetoric shift** | **Search** `include_domains=federalreserve.gov`, `freshness=month`, `livecrawl=web` → pull last 5 speeches' full text → **your** LLM hawkishness score. Or Research API w/ `output_schema` returning `{speech, date, hawkishness}` | ✅ **strong fit** | — |
| Real rate (10Y TIPS) | — | ❌ | **FRED `DFII10`** (free, direct) |

**Takeaway:** Rhetoric is your You.com showcase here. The rate *numbers* come from FRED/CME — don't fake them through search.

---

## Factor 2 — Bellwether Earnings Quality

| Sub-metric | You.com method | Verdict | Fallback |
|---|---|---|---|
| Est. revision momentum (NTM EPS now vs 90d ago) | Finance Research: current consensus is in-index (S&P Global). **90-days-ago** consensus is point-in-time → not retrievable | ⚠️ now ✅ / history ❌ | Paid estimates API (e.g. FMP estimates) for the lagged value |
| Growth deceleration (NTM growth − LTM realized) | Finance Research: *"NVDA NTM revenue growth vs LTM realized growth"* cited | ✅ | FMP fundamentals |
| GPU price proxy (H100/B200 spot, 30d chg) | Search + Contents on GPU-rental marketplaces / price trackers → extract $/GPU-hr | ⚠️ extraction-only, sources scrappy | Vast.ai / marketplace pages directly |
| **Guidance tone** | Finance Research to fetch latest **call transcript** → **your** LLM rubric score. Transcripts are in-index | ✅ **strong fit** | — |
| Miss tracker (displayed, lagging) | Finance Research: earnings surprises are in-index, cited | ✅ | — |

**Takeaway:** Guidance-tone + miss-tracker are clean You.com wins. The revision-momentum *history* is the one genuinely hard number — either approximate (current vs last reported) or pull from a paid estimates feed; be explicit in docs.

---

## Factor 3 — Circular / Off-Balance-Sheet Financing  ← your deepest showcase

| Sub-metric | You.com method | Verdict | Fallback |
|---|---|---|---|
| Footnote extraction (VIE, related-party, purchase obligations, vendor financing $) | **Research API**, `source_control.include_domains=["sec.gov"]`, `output_schema` = array of `{item, counterparty, amount_usd, filing_url, confidence}`. Or Finance Research `deep` (indexes filings) → parse | ✅✅ **best fit in the whole app** | — |
| Cross-check announced deals (equity stake + supply agreement) | Search `freshness=year` on deal news → corroborate the filing number | ✅ | — |
| Circularity graph + cycle detection | **Your** compute (networkx) over extracted edges | n/a | — |
| 1999 Lucent/Nortel/Cisco vendor-financing benchmark | Finance Research / Research on retrospective coverage → hardcode with citations | ✅ | — |

**Takeaway:** This factor is *made for* the Research API's `include_domains=sec.gov` + `output_schema` combo. Lead the technical demo here: typed dollar values, each with a filing URL, assembled into a cycle graph. Nothing else in the field will look like this.

---

## Factor 4 — Insider Selling & Lockup Supply

| Sub-metric | You.com method | Verdict | Fallback |
|---|---|---|---|
| Insider sell/buy ratio (Form 4, trailing 90d $) | Research `include_domains=["sec.gov"]` can read Form 4s, but aggregating $ across a universe from raw filings is heavy and error-prone | ⚠️ summary ✅ / precise aggregate ❌ | Dedicated insider API (e.g. FMP insider-trading) for the clean number |
| Founder/CEO mega-sales (>$100M announced) | Search / Finance Research — these are news-covered | ✅ | — |
| Supply overhang (secondaries + lockup expiries, next 90d) | Search for lockup-expiry dates & secondary announcements | ⚠️ dates ✅ / % of ADV ❌ | ADV is market data → **FMP** |

**Takeaway:** Qualitative insider narrative + mega-sale flagging = You.com. The precise trailing-90d aggregate ratio wants a dedicated feed; agentic extraction is demo-acceptable but flag the confidence.

---

## Factor 5 — Breadth & Concentration Divergence  ← mostly NOT You.com

| Sub-metric | You.com method | Verdict | Fallback |
|---|---|---|---|
| Top-10 S&P weight | Finance Research may return current, cited | ⚠️ | Index data / **FMP** |
| SPY − RSP 6m return | — | ❌ price math | **FMP / yfinance** |
| % of S&P above 200dma | — | ❌ | Compute from constituents (**FMP**) |
| 52wk H−L spread (NYSE) | Search can find a market-internals page | ⚠️ | FMP / market-internals source |

**Takeaway:** This is a **pure quant/price factor — compute it yourself from FMP** (`financialmodellingprep.com` is network-allowed). You.com adds nothing as source-of-truth here, and that's fine: F5 is deliberately your "we also do plain math correctly, no LLM in the loop" dimension and the anchor for the backtest. Don't force You.com into it.

---

## Factor 6 — Narrative Temperature  ← clean You.com win

| Sub-metric | You.com method | Verdict | Fallback |
|---|---|---|---|
| Hype-language density (live media) | **Search** `freshness=week`, `count=50`, `livecrawl=news` → gather ~N articles → **your** LLM classifies hype markers → density | ✅✅ **perfect fit** | — |
| 1999 press hype baseline | Search / Research on archived 1999–2000 coverage → score with same rubric → hardcode | ✅ | — |

**Takeaway:** Second-strongest You.com showcase after F3. Real-time news gathering is exactly what the Search API is for, and it's your most visual/innovative agent.

---

## Composite, analog matching, backtest, eval
All **your compute** (numpy / scipy / networkx). You.com supplies evidence, not math. Cosine/Mahalanobis/DTW on the feature vectors, cycle detection on the graph, the 2006–08 hold-out — none of that touches the API.

---

## What to actually buy from You.com vs external

**You.com is primary for (the demo's "agentic" spine):**
- Fed rhetoric scoring (F1) — Search + livecrawl
- Guidance-tone + miss tracker (F2) — Finance Research
- **Filing footnote extraction + circular dollars (F3)** — Research + `include_domains=sec.gov` + `output_schema`
- Insider narrative + mega-sales (F4) — Search / Finance Research
- **Live narrative temperature (F6)** — Search news + livecrawl

**External is source-of-truth for (don't route through You.com):**
- Real rates, historical rate series → **FRED**
- Fed-funds-futures-implied probabilities → **CME**
- All prices, index weights, breadth, ADV, %-above-200dma → **FMP** (network-allowed)
- Point-in-time consensus estimates & clean insider aggregates → paid finance API if you want them exact

**Net:** ~5 of 6 factors have a genuine You.com role; F5 is honestly external. That's a healthy, defensible split — you're using You.com where agentic research beats a data feed, and a data feed where it beats agentic research. Say exactly that in the pitch; it reads as senior judgment, not tool-worship.

---

## Endpoint quick reference (verified from docs)

| Endpoint | Host | Auth | Key params | Returns |
|---|---|---|---|---|
| Web Search | `GET https://ydc-index.io/v1/search` (POST variant for big domain lists) | `X-API-Key` | `query`, `count` (1–100), `freshness` (`day`/`week`/`month`/`year`/`YYYY-MM-DDtoYYYY-MM-DD`), `include_domains`, `exclude_domains`, `boost_domains`, `livecrawl` (`web`/`news`/`all`), `livecrawl_formats`, `country`, `offset` | `results.web[]`, `results.news[]` (each w/ `page_age`), `metadata` |
| Contents | `POST https://ydc-index.io/v1/contents` | `X-API-Key` | `urls[]`, `formats[]` (`html`/`markdown`/`metadata`), `max_age` (cache), `crawl_timeout` | `[{url,title,html,markdown,metadata}]` |
| Research | `POST https://api.you.com/v1/research` | `X-API-Key` | `input` (≤40k), `research_effort` (`lite`/`standard`/`deep`/`exhaustive`), `source_control{include_domains,exclude_domains,boost_domains,freshness,country}`, `output_schema` | `output.content` (md or JSON), `output.content_type`, `output.sources[]` |
| Finance Research | `POST https://api.you.com/v1/finance_research` | `X-API-Key` | `input` (≤40k), `research_effort` (`deep`/`exhaustive` only). **No** `source_control`/`output_schema` | `output.content` (md, `[[n]]`), `output.sources[]` |
| Account Balance | `GET .../v1/... billing` | `X-API-Key` | — | credit balance (poll to avoid overspend) |
| Live News | `GET https://api.ydc-index.io/livenews` | `X-API-Key` | `q`, `count`, `recency` (supports **datetime** ranges) | structured news | **❌ EARLY-ACCESS PARTNERS ONLY** — don't depend on it; Search `news` covers this |
| Agents (Express/Custom/Advanced) | `POST https://api.you.com/v1/agents/runs` | `Bearer` | `agent`, `input`, `stream`, `tools` | agent output items | **Beta.** Black-box — avoid; you want your *own* visible orchestration |

### `output_schema` rules (for the F3 evidence objects)
Root must be object; every object needs `properties` + `additionalProperties:false`; every property listed in `required`; optional = keep in `required` but nullable type `["number","null"]`; no `if/then/else` (use discriminated `anyOf` union nested under a property); no `min/max/pattern/format`; depth ≤5, ≤100 props. Your `{metric, value, unit, as_of, source_url, confidence}` fits cleanly — make `value`/`unit` nullable so unknowns return `null` not `""`.

---

## Credit budget (you get $100 free)

Per-call: Finance Research `deep` ≈ **$0.11**; Research `deep` **$0.10** / `standard` **$0.05**; Search **$0.005** (+livecrawl $0.001/page); Contents ≈ $0.001/page.

One full portfolio re-score (5 live names × F2+F3+F4 research calls + F1/F6 searches) ≈ **$3–4**. So:
- Keep the live universe small (5 names).
- **Cache hard** (`max_age`) and pre-compute the benchmark side once.
- Use `standard` not `deep` wherever the answer is easy.
- Mock the API during UI dev; only hit it for real integration + the demo.
- Poll the **Account Balance** endpoint so you don't get surprised mid-build.
Disciplined, $100 covers the whole hackathon with room to spare.
