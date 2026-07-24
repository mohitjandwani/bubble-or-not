# Bubble or Not — Implementation Plan (painter's passes)

Source of truth: `hackathon_handoff/` (HANDOVER.md governs; F3 spec = `f3-circularity-query-battery.md`; agent internals = `agents-README.md`; UI = `bubble-monitor-screen1-ui-spec.md`).

**Method:** every pass produces a *complete, runnable, manually testable system*. Pass 1 is the whole picture in rough strokes (all fake data). Each later pass swaps exactly one layer from fake→real or rough→detailed. At no point is there a "perfect hand on an empty canvas" — if the clock runs out after any pass, you still have a demoable whole.

**Cut line (from HANDOVER §9):** F1/F3/F5/F6 + 8 signatures ship; F2/F4 may stay `no-data` — the UI renders that honestly by design, so cutting them costs nothing structurally.

---

## At a glance

| Pass | Layer that becomes real | You can manually verify by… |
|---|---|---|
| 0 | API access | running two scripts, seeing cited JSON + real prices |
| 1 | **The whole picture, all fake** | opening the dashboard, clicking Rescore, watching fake numbers move |
| 2 | Database + pure-quant data (F5, rates) | quant strip matches Google Finance; reruns are identical |
| 3 | One real You.com agent + evidence trace | clicking a lamp → real quotes with real sec.gov/news URLs |
| 4 | All factors + signature engine + BTI | full run completes, 12 lamps with S:n W:n, real BTI |
| 5 | F3 showcase (registry, batteries, CMI, waterfall) | trace shows scan→verify fan-out; CMI sparkline; waterfall cited per bar |
| 6 | Deploy (Render ×2 + cron) | public URL works from your phone; curl rescore with admin key |
| 7 | UI detail pass (real charts + choreography) | 1200×630 screenshot of A+B self-explains; rescore animates |
| 8 | Eval + demo assets (+ Forge) | eval table σ<5; 60s backup recording plays; replay URL works |

---

## Pass 0 — Keys & ground truth (~30 min, tonight)

Nothing exists yet; just prove the two data planes work before building on them.

**Do:**
1. `YOU_API_KEY`, `FMP_API_KEY`, `ANTHROPIC_API_KEY`, `ADMIN_KEY` in `.env` (git-ignored).
2. `scripts/smoke_you.py` — the HANDOVER §9.1 verification, both ways:
   - Pattern A: Research API, `include_domains:["sec.gov"]`, binary-events `output_schema` (HANDOVER §4), input = the CoreWeave counterparty query (supplier concentration %, purchase commitments to NVIDIA, customer concentration, GPU-collateralized debt).
   - Pattern B: same text through Finance Research `deep` + FINDING template; print raw markdown + `sources[]`.
   - Print the account balance before/after.
3. `scripts/smoke_quant.py` — yfinance `^IXIC` 1996–2001 + 2023–now, `^TNX`; FMP index constituents + `federalFunds`. Print head/tail rows.

**Manual test:**
- [ ] Pattern A returns typed JSON (no prose) with sec.gov URLs; unknowns come back `null`, not `""`.
- [ ] Pattern B markdown contains `### FINDING` blocks with `[[n]]` markers and a `sources[]` list.
- [ ] Both eras of ^IXIC print real prices; FMP constituents list ~500 names.
- [ ] Balance visibly decremented by roughly the expected cost (~$0.10–0.25 total).

---

## Pass 1 — The rough full picture (walking skeleton, everything fake)

The entire product exists after this pass: monorepo, contract, all API endpoints, all six UI sections, polling, and a fake "run" you can trigger. No Postgres, no You.com, no chart libraries — plain boxes and numbers.

**Do:**
1. **Scaffold monorepo:** `/agents` `/dashboard` `/config` `/data/benchmarks` `/data/registry` `/eval` `/scripts`, plus root `schema.py` (the contract: Evidence, Probe, FactorResult, SignatureState, RunEvent, State payload — Pydantic).
2. **Config-as-code:** `/config/*.yaml` — factor weights, 12 signature configs (name, threshold text, strong/weak K, stage tag, placeholder 1999 precedent + citation slots), event→strength map, universe tickers, CMI weights, cadences. Fake values fine; *shape* final.
3. **Fixtures:** `data/fixtures/scores.json` + `evidence.json` matching `schema.py` exactly — a plausible full state (BTI 58, 5/12 fired, mixed lamps incl. one `no_data` hatched, one `partial`, evidence objects with fake-but-well-formed quotes/URLs/provenance).
4. **FastAPI (in-memory store):** all five endpoints from the contract — `GET /state[?run_id]`, `GET /events?since=`, `GET /evidence/{factor}`, `POST /rescore` (X-Admin-Key, 409 on concurrent via `asyncio.Lock`). `POST /rescore` launches a **fake pipeline**: an asyncio task that over ~15s emits the full `run_events` vocabulary (`run.started`, `agent.started`, `agent.tool_call`, `agent.evidence`, `agent.completed`, `run.completed`) and perturbs a few scores/lamps, then flips status back to idle.
5. **SPA rough draft** (Vite + React, or Replit Agent for the shell): sticky top bar + all sections A–F as rough blocks — BTI as a plain big number (no gauge yet), 12 dots, templated stage sentence, hero chart as an empty placeholder box, full signature board (groups, lamps as colored circles, S:n W:n counters, precedent/current text, click → evidence drawer table), radar/thermometer placeholders, quant strip cards with fixture numbers, footer. Polling loop per spec: `/state` 2s while running / 15s idle; diff consecutive payloads and at minimum re-render what changed.
6. **Mock switch:** `MOCK=1` env — everything network-external stays fake behind one flag from day one.

**Manual test:**
- [ ] `uvicorn` + `npm run dev` → dashboard renders all six sections from fixtures; nothing blank.
- [ ] Click every one of the 12 signature rows → drawer opens with evidence table + provenance line; opening another closes the first.
- [ ] `curl -X POST -H "X-Admin-Key: …" /rescore` → within 2s the page notices `status=running`; over ~15s numbers/lamps change; a second POST during the run returns **409**.
- [ ] `GET /events?since=0` returns the fake trace; `?since=<mid-id>` returns only later rows.
- [ ] The `no_data` row renders hatched with its honest tooltip.

---

## Pass 2 — Real bones: Postgres + pure-quant factors (F5 + F1 rates + hero data)

Swap the in-memory store for the real DB, and make everything that needs **zero LLM** real. This is the "fast real-data win" and it de-risks the schema.

**Do:**
1. `schema.sql` = the DDL from agents-README §6 verbatim (runs, run_events, evidence, factor_results, signatures, registry_edges, probe_cache). Local `docker run postgres:16`; asyncpg pool 5–10; one short transaction per probe write; recreatable in one command.
2. Port the API to read from Postgres; fake pipeline now writes real rows (this proves replay: `GET /state?run_id=` of a past fake run).
3. **Probe abstraction** (`agents-README §2`) + orchestrator lifecycle (preflight → gather → reduce → finalize), with all probes still fake *except*:
4. **QUANT probes real:** F5-top10, F5-eqw (SPY−RSP 6m), F5-200dma, F5-tnx, F1-rates — FMP/yfinance, methodology §F5/§F1 formulas, `norm()` helpers, deterministic `f5` sub-score.
5. **Benchmark series:** pull 1996–2001 and 2023–now ^IXIC weekly (downsampled server-side) + fed-funds series → `/data/benchmarks/*.json`, served inside `/state` (≤200KB budget).
6. Quant strip (Section E) binds to real values + real sparklines (plain polyline is fine).

**Manual test:**
- [ ] `psql -f schema.sql` on a fresh DB → clean; run a rescore → rows appear in `runs`, `run_events`, `evidence`, `factor_results`.
- [ ] Quant strip: top-10 weight, SPY−RSP, %>200dma, ^TNX match a spot-check against public sources (±rounding).
- [ ] Two consecutive runs (same market close) produce **identical** F5 scores — determinism proof.
- [ ] `GET /state?run_id=<older>` replays the earlier run's numbers.
- [ ] Kill FMP key → F5 renders stale-not-blank ("stale · <ts>" chip, dimmed last-good score).

---

## Pass 3 — First real agent, end to end (evidence you can click)

One vertical slice of the agentic spine: a real You.com call → typed evidence → signature lamp → drawer with real citations → trace events. Once one probe flows, the rest are repetition.

**Do:**
1. **You.com client** (`/agents/youcom.py`): search / contents / research / finance_research + balance; retries, cost accounting per call, `probe_cache` honoring `ttl_hours`, `cache_hit` events.
2. **Pattern A live:** F2-B1 strong binary + F2-B2 weak binary (HANDOVER §4 questions + schema, `standard` effort, explicit `YYYY-MM-DDtoYYYY-MM-DD` freshness windows).
3. **Signature engine v1:** config event→strength re-map (LLM label advisory only), deterministic aggregation `strong≥1→FIRED / weak≥K→PARTIAL / else WATCH`, `S:n W:n` counters, `driving_evidence_ids`.
4. **Shared `extract()`** (Pattern B chain: regex `### FINDING` split → field parse → Haiku fallback on failed blocks only → Pydantic validate with one retry → `[[n]]`→URL mapping). Wire **one** Pattern B probe live to prove it: F2-tone-NVDA. Log raw md + parsed objects into `run_events.detail`.
5. Evidence drawer + Screen-2-style trace list (rough) now read real rows.

**Manual test:**
- [ ] Rescore with `MOCK=0` for F2 only: trace shows `agent.tool_call` with endpoint/params/cost/elapsed, then `agent.evidence{count}`.
- [ ] Click the F2 binary signature row → real quotes, real URLs; open 3 URLs → they resolve and contain the quoted material.
- [ ] The lamp state is explainable by hand from the counters and config K — recompute it yourself.
- [ ] Re-run within TTL → `cache_hit=true` events, balance unchanged.
- [ ] Feed `extract()` a deliberately mangled FINDING block → confidence=low, excluded from score, visible in trace (not crashed).

---

## Pass 4 — All factors rough + real BTI (the picture is now real, still unrefined)

Fan out the pattern from Pass 3 to every factor. Accuracy of prompts/thresholds can still be rough — the goal is that *every* number on screen is real or honestly `no-data`.

**Do:**
1. **F1 rhetoric:** Search `include_domains=federalreserve.gov` + livecrawl → last 10 speeches → Haiku rubric (agents-README §5.3, temp 0) → delta = mean(last 5) − mean(prior 5). Combine with Pass-2 rates per methodology §F1 (futures-implied sub-metrics: FMP-derived or `no-data`, never faked).
2. **F2 full:** tone ×8 tickers (Pattern B, shared `extract()` + §5.4 scorer), GPU-spot (Search+Contents, 30d), revision/growth via Finance Research (history unavailable → approximate + flag, or `no-data`), miss tracker display-only.
3. **F4:** insider narrative + mega-sale count (Pattern B/Search), confidence=medium flagged; precise aggregates honestly `no-data`.
4. **F6:** Search `freshness=week` `count=50` + livecrawl → §5.5 hype classifier (batched, skeptic-exclusion) → density vs cited 1999 baseline (research once, hardcode in config).
5. **Scoring reduce:** methodology formulas F1–F6 → `BTI = .25·F1+.20·F2+.20·F3+.15·F4+.20·F5` (F3 still fake until Pass 5) → stage-sentence template over stage-buckets → delta vs `prev_bti`.
6. **Signature configs finalized:** research the 12 precedents via You.com once, hardcode text+citations+thresholds in `/config` (HANDOVER §9.4).
7. Per-agent `asyncio.wait_for` timeout + try/except → stale-not-blank; endpoint semaphores (search 5, research 3); preflight budget/priority dropping.

**Manual test:**
- [ ] Full `MOCK=0` rescore completes < ~4 min; `run.completed` shows real BTI + changed signatures; total cost logged ≈ $0.60–2.20 and matches balance delta.
- [ ] All 12 rows populated: every lamp is fired/partial/watch/not from real evidence, or hatched `no_data` — zero fake values anywhere.
- [ ] Stage sentence reads correctly from fired buckets (change a config threshold, re-run, sentence updates).
- [ ] Unplug one factor (bad key) mid-run → that factor stale, run still completes, BTI computed from last-good.
- [ ] Spot-check 5 citations across factors → URLs contain the claims.

---

## Pass 5 — F3 showcase (the detailed brushwork the judges inspect)

The genuinely agentic factor: registry, two-stage battery, verify fan-out, CMI, waterfall.

**Do:**
1. **Registry seed:** research ~10–15 edges via You.com (NVDA↔neocloud, hyperscaler↔lab, SPVs, lab→startup funds) → `/data/registry/edges.yaml` with citations → load into `registry_edges` (`ON CONFLICT` upsert).
2. **Stage1Agent** (weekly battery §6): S1-B1/B2 binaries, S1-Q1 formation scan → §5.6 entity extraction → dedup vs registry → **fan-out S1-Q2 verify ×≤6** → upsert verified/announced_only; S1-Q3 credit-pool, S1-Q4 destruction (canary), S1-Q5 ARR, S1-Q6 repricing.
3. **Stage2Agent** (monthly battery §7): S2-B1/B2, S2-Q1 formation, **S2-Q2 counterparty verification** (Research `deep` + sec.gov + F3 schema — the flagship probe), S2-Q3 leverage, S2-Q4 SPV, S2-Q5 distress (avalanche), S2-Q6 vendor aggregates sanity check (Σ edges ≤ aggregates else flag), T-Q1 triangles.
4. **Cold-start battery (mandatory, run the night before demo):** every query once, wide windows (S1 month / S2 year) → window-0 baselines persisted. No baseline = no delta on demo day.
5. **CMI:** `w_f·norm(Δformation) − w_d·norm(Δdestruction) + w_i·Δintensity` per stage from identical windowed re-runs; F3 sub-score = CR 50% + CMI_s2 25% + CMI_s1 25%; the 4 F3 signatures + "canary before avalanche" composite.
6. **Revenue Quality Waterfall:** per lab (OpenAI | Anthropic), ARR − portfolio-customer floor − credit-inflation range − committed-vs-recognized gap → band + RQ score; rough bar rendering in the F3 drawer, citation chip per bar.
7. UI: two-line CMI sparkline in the F3 group header; edge list with verified/announced-only (dimmed)/contradicted states.

**Manual test:**
- [ ] Trace shows the money shot: one S1-Q1 scan event expanding into N parallel S1-Q2 verify events.
- [ ] Registry rows show status transitions; an announced-only edge is dimmed and provably excluded from CR (recompute CR by hand from verified edges / total assets).
- [ ] Run the battery twice with two adjacent windows → CMI deltas are computed from the pair, not a single run.
- [ ] Waterfall: every bar has a citation chip; RQ score = band midpoint / reported ARR by hand-check.
- [ ] S2-Q2 evidence quotes exact filing sentences with sec.gov URLs.

---

## Pass 6 — Deploy (don't discover Render on demo day)

**Do:**
1. Render: Postgres + **paid** web service (free tier spins down + no disk — HANDOVER §10 gotcha) + static site for the SPA; env vars set; `schema.sql` applied.
2. Render Cron 6h → `POST /rescore` (cadence config decides which batteries actually fire).
3. `runs.config_version` = git SHA of `/config`; CORS locked to the SPA origin; SPA can never trigger agents (admin key server-side only).
4. Buy/point the domain.

**Manual test:**
- [ ] Public URL loads on your phone; polling works; no console errors.
- [ ] `curl -X POST https://…/rescore -H "X-Admin-Key: …"` from your laptop → live run visible on the public page.
- [ ] Wrong/missing admin key → 401/403. Two rescores → 409.
- [ ] Wait 20+ min idle, reload → instant (no cold-spin).
- [ ] Cron fires (temporarily set a near-term schedule, then restore 6h).

---

## Pass 7 — UI detail pass (rough blocks → the spec'd picture)

Now, and only now, the fine brushes. Do it against the deployed API. Order from the UI spec: C polish → A → B → E → D → choreography.

**Do:**
1. **Section A:** bespoke SVG half-donut gauge with zones + needle sweep + count-up; dot-fuse with hover/click-scroll; sentence crossfade.
2. **Section B (hardest — budget most):** dual-timeline indexed chart, phase-aligned axes (1996-01→2001-12 bottom, 2023-01→now top), amber vs bright grammar, post-peak segment at 55% opacity, signature pins + ghost slots + collision stacking, synced crosshair, `Price | Rates` crossfade toggle, pin-click → row flash.
3. **Section D:** Recharts radar (today filled vs dashed danger outline, breach fill red, vertex interactions) + bespoke SVG thermometer with rotating sampled phrases + "coincident — display only" badge.
4. **Choreography:** client-side diff of consecutive `/state` payloads → gauge pulse/count, staggered dot flips, lamp pulses, pin fall-in, radar morph, sparkline append. Idle = perfectly still.
5. Polish: tabular mono numerals, source chips everywhere, hover states, spacing, color grammar (amber/bright/red/hatched) audited across all sections.

**Manual test:**
- [ ] Screenshot A+B at 1200×630 → self-explanatory with zero interaction (this is the OG image — save it).
- [ ] Trigger a live rescore while watching: full choreography plays once, page is motionless before and after.
- [ ] Rates toggle crossfades with no layout shift; crosshair shows both eras' values at the same phase %.
- [ ] Every number on the page has a source chip that opens the right URL.
- [ ] Page JSON payload ≤ ~200KB; no zoom/pan/date-pickers snuck in.

---

## Pass 8 — Eval, demo assets, and the Forge play

**Do:**
1. **Eval harness (`/eval`):** 3 back-to-back runs → variance per factor (target σ<5), citation-validity spot-check (N=10, HTTP 200 + claim present), extract-chain failure rate, cost per factor — four SQL queries; publish table at the bottom of `/agents/README.md` + one slide.
2. **`/agents` README:** finalize — probe registry, prompts, DDL, API contract, eval table. This is the artifact the You.com judge reads.
3. **Demo insurance:** pick the best past run → memorize/bookmark `GET /state?run_id=` replay URL; record 60s backup screen capture; export architecture diagram (mermaid → image).
4. **Opsera Forge (time-boxed 45 min, $500 prize):** verify at booth that work orders can wrap changes to an existing repo; gate a `/config` change through a work order; screenshot the audit trail + ForgeScore; join `runs.config_version` → work order for the "who approved this rubric" slide. Fallback: Forge a smaller artifact (schema module or eval harness).
5. **Pitch:** rehearse ×2 with the live-rescore choreography; keep the stage lines from HANDOVER §1; last 2h locked for this.

**Manual test:**
- [ ] Eval table renders from real queries; σ<5 or the outlier factor is explained on the slide.
- [ ] Kill the backend → replay URL + backup recording still tell the story.
- [ ] A stranger (or you, cold) can follow the 3-min demo path: headline → verdict → drawer → trace → eval slide → stage sentence.
- [ ] Forge screenshots + config_version join captured for submission.

---

## Working rules (apply to every pass)

- **LLMs gather evidence; scores are computed.** Never let a model emit a score or a lamp state.
- **`MOCK=1` during all UI work**; real API calls only for integration tests and the demo. Poll balance; full rescore ≈ $0.60–2.20, budget $100.
- **Stale-not-blank, disagree-not-average, no-data-not-fake** — the three honesty rules are features; test them deliberately in each pass.
- **Freshness = explicit `YYYY-MM-DDtoYYYY-MM-DD` ranges; query text never mentions dates.** Client-side `page_age` + event-date checks layered on top.
- Commit after every green manual test; `/config` changes get their own commits (Forge audit story depends on it).
