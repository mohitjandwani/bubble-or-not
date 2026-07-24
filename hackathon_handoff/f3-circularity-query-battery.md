# F3 Circularity — Query Battery v2 (You.com)

Final F3 spec: archetypes, registry, two-stage CMI, signal taxonomy, binary-question battery, structured-markdown extraction. Supersedes F3 in the methodology doc.

---

## 1. Archetype model (hardcoded config)

| # | Archetype | Mechanism | Where each element lives |
|---|---|---|---|
| A | Equity-for-revenue | Vendor invests in customer → customer buys vendor's product with vendor's money (NVDA→neocloud) | Deal + size: press. Vendor side: 10-K aggregate equity (scale check only — vendors disclose aggregates WITHOUT attribution). **Counterparty side (where attribution lives): S-1/10-K supplier concentration %, purchase commitments $, "Customer A = X% of revenue"** |
| B | Offtake/backstop | Vendor guarantees to rent back unused capacity → customer revenue de-risked by its own supplier | Counterparty filings (commitments) + press |
| C | Compute-for-equity triangle | Chip vendor → AI lab equity → lab compute commitment → spend flows back via cloud | Press per leg; cloud capex disclosures. Track cash vs in-kind per leg |
| D | GPU-collateralized debt | Private credit lends against GPU collateral → purchase financed by asset's own resale value | Debt announcements, ratings commentary, press |
| E | SPV/JV datacenters | Capacity commitments via unconsolidated entities → obligations off balance sheet | 10-K purchase-obligation/lease footnotes + press for structure |
| F | **Lab→startup revenue recycling** | Lab invests in / credits startups → startups buy tokens → lab "revenue"/usage | Fund announcements + case-study pages + press ARR figures. **Accounting split: free credits = usage/ARR-story inflation, NOT GAAP revenue · investment-funded spend = real booked revenue, cash-circular · cloud-partner in-kind = multi-hop (C)** |

## 2. Known-deal registry (seed tonight)

~10–15 typed edges, press-covered, hardcoded with citations:
`{edge_id, from, to, archetype, announced_amount_usd_m, date, seed_source_url, status}`
Status: **verified** (press + counterparty-filing corroboration → scored) · **announced-only** (press only → displayed dimmed, unscored) · **contradicted** (flagged) · **unverified** (scanner candidates, dimmed layer).
Coverage: NVDA↔neocloud complex · hyperscaler↔lab equity+compute pairs · major SPVs · OpenAI Startup Fund / Anthropic program → API-customer deals.

## 3. Two-stage model & CMI

| | Stage 1 — usage layer | Stage 2 — GPU/capex layer |
|---|---|---|
| Loop | Lab→startup→tokens (archetype F) | Vendor→neocloud→GPUs (A–E) |
| Edge size / count | $1M–100M, many | $1B–100B, few |
| Cadence | **weekly** — churns fast, breaks first (canary) | **monthly** — discrete shocks, breaks second (avalanche) |

**CMI_stage = w_f·norm(Δformation) − w_d·norm(Δdestruction) + w_i·Δintensity** — deltas between identical windowed re-runs (never one run). Weights in config.
**Composite pre-break signature: Stage-1 CMI < 0 while Stage-2 CMI > 0.**
F3 sub-score: Circularity Ratio (verified circular $ in detected cycles / total assets; tiers <1% normal · 1–3% ≈1999 vendor-financing · >3% exceeds) **50%** · CMI_stage2 **25%** · CMI_stage1 **25%**.

## 4. Signal taxonomy (governs all queries below)

**Strong** (company against own interest): guidance_cut, guidance_withdrawn, reported_miss (vs own guidance), impairment, order_cancellation, covenant_issue. One suffices.
**Weak** (third-party/proxy): analyst_estimate_cut, price-target cuts, GPU spot drift, "people familiar" reports, contract-renegotiation rumors. Cluster required.
```
strong >= 1                -> FIRED
weak >= K (config, ~3)     -> PARTIAL ("cluster forming")
weak 1..K-1                -> WATCH (count shown)
```
Weak moves first, strong confirms → expected sequence weak-cluster → strong. Event→strength map lives in config; LLM only extracts events. UI counters `S:n W:n` per signature row.

## 5. Recency layering (every delta query)

1. `freshness` / `source_control.freshness` — **explicit ranges `YYYY-MM-DDtoYYYY-MM-DD`** for reproducible non-overlapping windows
2. client-side `page_age` filter
3. extracted event-date vs window (fresh article about old deal ≠ formation)
Query text = content only, never dates.

---

## 6. STAGE 1 battery (weekly)

**S1-B1 · Strong binary (Pattern A: Research `standard`, output_schema = binary-events schema in HANDOVER §4, freshness = window):**
- "In this period, has any publicly traded neocloud or AI infrastructure company (CoreWeave, Nebius, ...) lowered or withdrawn its own revenue, cash flow, or capex guidance?"
- "In this period, has any AI lab's reported revenue metric changed definition (e.g., 'annualized run-rate' vs recognized revenue) in official or press statements?" → drift = mid-stage signature
**S1-B2 · Weak binary (same pattern):**
- "In this period, have analysts cut revenue/EPS estimates or price targets for neoclouds or AI-exposed infrastructure names?"
- "In this period, are there reports of AI API spending being cut, startups reducing token usage, or renegotiating model contracts?"
**S1-Q1 · Formation scan (Search, `livecrawl=news`, count=30):** `OpenAI Startup Fund OR Anthropic investment new startup announcement API customer` (+variant `AI lab invests startup "built on" GPT OR Claude`). Extract candidate F-edges → delta count+$.
**S1-Q2 · Edge verification (Research `standard` per candidate):** "Is <STARTUP> both an investee of <LAB>'s fund/credit program AND a paying API customer? Investment announcement + independent usage evidence (case study, blog, press). Cite URLs+dates." Verified only → CMI.
**S1-Q3 · Credit-pool (Search, month window):** `OpenAI OR Anthropic startup program free credits expansion accelerator cohort` → credit-pool estimate delta (usage-inflation bucket, not revenue).
**S1-Q4 · Destruction — THE CANARY (Search, `livecrawl=news`, count=30):** `AI startup shutdown OR winding down OR acquihire OR pivots away API costs` (+`AI wrapper startup failed burn rate token costs`). Cross-check registry; destruction delta = highest-frequency break signal. ≥threshold for 2 consecutive weeks → "usage-layer churn accelerating" (early signature).
**S1-Q5 · ARR tracker (Search, month):** `OpenAI OR Anthropic annualized revenue run-rate latest` → newest figure + exact metric phrase → waterfall denominator + drift detection.
**S1-Q6 · Repricing (Search, month):** `OpenAI OR Anthropic API price cut discount enterprise minimum spend` → price↓ + credits↑ = negative intensity.

## 7. STAGE 2 battery (monthly)

**S2-B1 · Strong binary (Pattern A):**
- "In this period, has NVIDIA or AMD lowered its own guidance or has management softened forward demand language in official communications?"
- "In this period, has any neocloud reported revenue or operating cash flow below its own prior guidance, taken an impairment, or disclosed a covenant issue?"
- "In this period, has any announced GPU order, datacenter buildout, or capacity contract been canceled, delayed, or renegotiated by the companies involved?"
**S2-B2 · Weak binary:** analyst cuts on NVDA/neocloud complex · GPU spot-price decline reports · short-seller theses on circular financing.
**S2-Q1 · Formation (Search, `livecrawl=news`, count=30):** `NVIDIA OR AMD investment neocloud equity stake purchase agreement GPUs` (+`chipmaker backstop capacity agreement rent unused GPU`). New A/B edges → formation $.
**S2-Q2 · Counterparty verification (Pattern A: Research `deep`, `include_domains:["sec.gov"]`, F3 output_schema):** "From <COUNTERPARTY>'s most recent 10-K/10-Q/S-1: supplier concentration %, purchase commitments to <VENDOR> $, customer concentration, debt secured by GPU collateral. Quote exact sentences + filing URLs." → the only scored edge values.
**S2-Q3 · Leverage (Search, month):** `GPU-backed loan OR debt facility neocloud private credit collateral financing` → new facilities; rate/haircut tightening = destruction-side.
**S2-Q4 · SPV formation (Search, month):** `data center SPV joint venture special purpose vehicle AI capacity lease hyperscaler` → off-BS commitments.
**S2-Q5 · Distress — THE AVALANCHE (Search, `livecrawl=news`, count=30):** `neocloud OR AI data center canceled OR delayed OR renegotiated GPU order impairment writedown covenant`. Any registry-edge hit → heavy negative CMI + "capex-layer edge distress" (late signature).
**S2-Q6 · Vendor aggregates (Pattern B: Finance Research `deep` + FINDING template, quarterly):** "In NVIDIA's latest quarterly filing and earnings call: total non-marketable equity investments, purchase/supply commitments, customer concentration disclosures, and management commentary on customer financing. Quote figures with sources." → scale sanity check (Σ verified edges ≤ aggregates, else flag).
**T-Q1 · Triangle legs (Research `standard`, monthly, per known triangle):** "Trace announced relationships among <CHIP VENDOR>, <CLOUD>, <LAB>: investment amounts, compute commitments, cloud-credit components. Cite per leg; note cash vs in-kind." → in-kind share rising = intensity↑.

## 8. Archetype F exhibit — Revenue Quality Waterfall

Per lab (OpenAI | Anthropic — identical methodology, stated on the slide):
```
Reported ARR (S1-Q5, cited)
 − revenue from equity-portfolio customers   [verified F-edges → LOWER BOUND, cited]
 − credit-cohort usage inflation             [S1-Q3 estimate range; labeled "not GAAP revenue"]
 − committed-not-recognized gap              [announced TCV vs run-rate, where reported]
 = cash-quality revenue BAND (min–max whiskers)
Revenue Quality Score = band midpoint / reported ARR
```
Waterfall chart, uncertainty whiskers, citation chip per bar, side-by-side labs. 1999 precedent (cited): barter/ad-swap revenue + Lucent/Nortel vendor financing. Framing: "we compute the floor, not the truth."

## 9. F3 signatures (into the 12-row board)

| Signature | Trigger | Stage |
|---|---|---|
| Usage-layer churn accelerating | S1-Q4 destruction ≥ threshold 2 consecutive weeks | early |
| Revenue definition drift at labs | S1-B1 drift event | mid |
| Vendor-financed revenue material | Circularity Ratio ≥ tier-2 OR RQ score ≤ threshold | mid |
| Capex-layer edge distress | any S2-Q5/S2-B1 strong on registry edge | late |
Plus composite: Stage-1 CMI < 0 while Stage-2 > 0 → "canary before avalanche" callout on the CMI sparkline.

## 10. Evidence & cost

Evidence object: `{stage, query_id, window, metric: formation|destruction|intensity|binary, value, events[], edges[], sources[], provenance}`. All parsing via shared `extract()`; binary answers via output_schema (no parsing).
Cost/cycle: Stage 1 ≈ $0.20/wk · Stage 2 ≈ $0.50/mo. Registry build = one-time.

## 11. Cold-start (tonight — mandatory)

Run every query once with wide windows (S1: month · S2: year) → window-0 baselines + registry seed. **No baseline = no delta = no direction on demo day.**
