# Bubble or Not — Screen 1 ("The Verdict") — Full UI Specification

Version 1.0 · Companion to `bubble-monitor-methodology.md` and `bubble-monitor-data-sourcing.md`

---

## 1. Purpose & design principles

Screen 1 is the public dashboard. It must:
1. Answer "is this a bubble, and is it about to pop?" in one glance (verdict header).
2. Prove every claim with a visible citation (source chips everywhere).
3. Work as a standalone screenshot above the fold — that's what gets shared.

Principles:
- **One page, vertical narrative, no navigation** except the Verdict/Engine tab switch.
- **Signature checklist over pseudo-precision** — where 1999 data doesn't exist in our allowed sources (You.com, FMP, yfinance), we show a cited 1999 *signature* + today's reading, never a fake continuous line.
- **Calm when idle, animated only on state change** — motion is reserved for the live rescore demo.
- **Evidence, not advice** — footer disclaimer; language throughout is "conditions resemble," never "sell."

Allowed data sources: **You.com APIs** (Search, Contents, Research, Finance Research), **financialmodelingprep (FMP)**, **yfinance**. Anything unavailable in these → signature marked `no-data`, rendered honestly, never faked.

---

## 2. Global layout

- Fixed content width ~1200px, centered; dark theme (near-black background `#0B0E14`-class, financial-terminal aesthetic).
- Vertical section stack:

| # | Section | Height | Question it answers |
|---|---------|--------|---------------------|
| A | Verdict header | ~220px | What's the answer? |
| B | Hero overlay chart | ~420px | Show me. |
| C | Signature board | auto (rows expand) | What's the evidence? |
| D | Radar + Narrative thermometer | ~380px, 60/40 split | What shape are we in now? |
| E | Quant strip | ~160px, 4 cards | Raw numbers, no LLM |
| F | Footer | ~80px | Methodology, disclaimer |

### Sticky top bar (56px)
- Left: wordmark **"Bubble or Not"** + domain.
- Center: **BTI mini-gauge** (number + colored dot) — persists while scrolling.
- Right: `last updated 14:32 PT` · tabs **Verdict | Engine**.
- On rescore: mini-gauge pulses and counts to the new value.

### Color & typography grammar (used everywhere)
| Meaning | Treatment |
|---|---|
| 1999 / historical | muted amber `#C8933A`-class, dashed or dimmed |
| Today / live | bright white/cyan, solid |
| Fired / breached / danger | red `#E5484D`-class |
| Partial | yellow |
| Not fired / calm | neutral gray |
| No data (skipped) | hatched gray ▨ + tooltip explaining the gap |
| Source attribution | small "chip": favicon + domain, click → URL |

Numeric font: tabular mono for all figures. Headings: tight geometric sans.

---

## 3. Section A — Verdict header

Three elements on one horizontal band (grid: 320px / auto / 400px):

### A1. BTI gauge (left)
- Half-donut 0–100, needle at current composite BTI.
- Zones: 0–40 calm (gray-green) · 40–70 elevated (amber) · 70–100 danger (red).
- Beneath: large BTI number (tabular, ~56px) + delta chip since previous run (`+3 ▲` red-tinted if rising).
- Data: computed BTI from pipeline (deterministic weighted sum, see methodology §Composite).
- Rescore animation: needle sweeps from old to new over ~1.2s, number counts up.

### A2. Signature counter (center)
- Headline: "**7 / 12** signatures fired".
- Below: 12 dots in factor order, colored by state (red/yellow/gray/hatched). Hover a dot → signature name + state.
- Acts as a glanceable fuse; dots are anchors — click scrolls to that row in Section C.

### A3. Stage statement (right)
- One plain-English sentence, template-generated from state, e.g.:
  > "Conditions resemble **mid-stage 1999**. Late-stage triggers — bellwether cracks, insider selling wave — have **not fired**."
- Second line, smaller: which factor moved most in the last run ("Driven by: Liquidity +2.1").
- Rule: sentence templates are deterministic functions of (count fired, which stage-buckets fired); never free-generated at render time. Late-stage signatures are tagged in config; stage = early/mid/late by which buckets have fired.

---

## 4. Section B — Hero overlay chart

### Chart type
Dual-timeline indexed line chart. Two x-axes sharing the same pixel span:
- Bottom axis: **1996-01 → 2001-12** (historical era).
- Top axis: **2023-01 → today** (current era).
Eras align by *phase position* across the shared width, not by calendar mapping.

### Series
| Series | Style | Data |
|---|---|---|
| 1999 era: Nasdaq Composite (^IXIC), indexed to 100 at 1996-01 | muted amber, 2px; post-peak crash segment at 55% opacity ("the road ahead") | yfinance daily, downsampled to weekly |
| Current era: Nasdaq (^IXIC) or S&P (^GSPC) — config, default Nasdaq | bright, 2.5px; terminal point = pulsing live dot | yfinance daily → weekly; last point refreshed each run |

### Signature pins
- On the 1999 line: a pin (▼) at each date a signature historically fired. Hover → tooltip: signature name, date, one-line description + citation chip. Pin dates come from the signature config (researched via You.com, hardcoded with citations).
- On the today line: matching pin only where that signature has fired now (red ▼); unfired signatures show as faint ghost slots at the phase-equivalent position — **the visual punch is the pins 1999 has that today doesn't yet.**
- Pin collision: stack vertically with 4px offset when within 8px horizontally.

### Toggle (top-right of chart)
`Price | Rates`
- **Rates view**: same dual-timeline. Series = fed funds effective rate as **change from cycle start** (pp), both eras. 1999: cycle start = 1999-06 first hike. Today: cycle start = config (current cycle anchor). Pins = hike/cut dates. Data: FMP economic indicators (`federalFunds`) or yfinance `^IRX` proxy; whichever resolves cleanest — decided at build, one source, cited in tooltip.
- Toggle is a crossfade (250ms), no layout shift.

### Interactions
- Hover crosshair: vertical line synced across both eras at the same phase %, tooltip shows both values + both dates.
- Click a pin → scrolls to and flashes that signature's row in Section C.
- No zoom/pan (scope control).

### States
- Loading: skeleton line shimmer.
- Data gap (yfinance/FMP failure): render last cached series + "stale · as of <ts>" badge; never blank.

---

## 5. Section C — Signature board (core module)

### Structure
5 factor groups → 12 signature rows total. Group order = factor importance: F1 Liquidity, F2 Bellwethers, F3 Circular financing, F4 Insiders, F5 Breadth.

### Factor group header
- Factor name + one-line description.
- Slim horizontal bar = factor sub-score 0–100 (fills with zone color). Right-aligned: numeric sub-score + weight chip ("25%").
- The board therefore doubles as the factor breakdown — no separate breakdown widget needed.

### Signature row anatomy (left → right)
| Element | Spec |
|---|---|
| Status lamp | 16px circle: red = fired · yellow = partial · gray = not fired · hatched = no-data. Pulses once when state changes on rescore. |
| Signature name | Bold, ≤6 words, e.g. "Estimate revisions turn negative" |
| 1999 precedent | Muted amber text, one line + citation chip. E.g. "Revisions decelerated ~2 quarters pre-peak 〔chip〕" |
| Current reading | Bright text, one line + source chip. E.g. "Median bellwether NTM revision +1.8% — still positive 〔chip〕" |
| Confidence dot | 3-state (high/med/low) from evidence confidence; tooltip explains |
| Fired-when | Tiny right-aligned rule text on hover: the exact threshold, e.g. "fires when median revision < 0 for 2 consecutive checks" |

Rule: fired/partial/not is a **deterministic threshold over stored evidence values**, defined per signature in config — never an LLM verdict at render time.

### Evidence drawer (row click)
Slides open below the row (280–400px):
- **Evidence objects table**: metric · value · unit · as-of · confidence · source (chip). Rows come straight from the typed evidence store.
- **Quoted snippet** per object (from the API's source snippets), styled as a quote with the URL.
- **Provenance line**: which endpoint produced it — e.g. `Research API · include_domains: sec.gov · deep · $0.10 · 12.4s` — quiet engineering proof on the public screen.
- Disagreement state: if two evidence objects conflict, both shown with a ⚠ "conflicting sources — excluded from score" banner.
- One drawer open at a time; opening another closes the previous.

### No-data rows
Rendered in place (never hidden): hatched lamp, current reading = "Not measurable from allowed sources", tooltip states exactly what's missing (e.g. "point-in-time 1999 consensus estimates unavailable"). Honesty is a feature.

---

## 6. Section D — Radar + Narrative thermometer (60/40 two-up)

### D1. Radar (left)
- 5 axes = F1–F5 sub-scores, 0–100, factor order clockwise from top.
- Two shapes:
  - **Today**: filled bright polygon, 25% fill opacity, solid vertex dots.
  - **Danger thresholds**: dashed neutral outline — per-factor level historically consistent with late-stage conditions (from signature config, cited).
- Where today's polygon exceeds the threshold outline, the overlap region fills red — breached spokes are instantly visible.
- Vertex hover → factor name, score, threshold, "breached by +12".
- Vertex click → scrolls to factor group in Section C.
- Rescore animation: polygon morphs to new shape (400ms ease).

### D2. Narrative thermometer (right)
- Vertical thermometer 0–100 = hype-language density index (F6), today's fill vs a tick mark labeled "1999 peak baseline 〔chip〕" (cited, from You.com research on archived-coverage samples).
- Below: 2–3 rotating sampled phrases from this week's media, each with source favicon + count, e.g. "'this time is different' — 14 mentions this week 〔chips〕". Rotation every 6s, pause on hover.
- Permanent badge: **"Coincident indicator — display only, excluded from BTI."**
- Data: Search API `freshness=week` + livecrawl → classifier → density; phrases are top-N classifier hits with URLs.

---

## 7. Section E — Quant strip ("no LLM in this row")

Four uniform cards, equal width. Each card: label · big current number (tabular) · 12-month sparkline · threshold tick on the sparkline scale · tiny source chip.

| Card | Metric | Data | Threshold tick |
|---|---|---|---|
| 1 | Top-10 S&P 500 weight | FMP index constituents + market caps | config, cited |
| 2 | Cap vs equal-weight gap | SPY − RSP trailing 6-mo return (yfinance) | 0pp line + danger level |
| 3 | % above 200dma | FMP constituent prices, computed | participation danger level |
| 4 | 10Y Treasury yield | yfinance `^TNX` | 6-mo change annotated |

- Strip caption (left-aligned, small): *"Computed directly from market data — no model in the loop."*
- Card hover → exact as-of timestamp + computation one-liner.
- These four also feed F5's sub-score; the strip is their raw display.

---

## 8. Section F — Footer

- Left: "Methodology" link (→ repo README anchor) · "Built on You.com Research APIs" with logo · GitHub link.
- Center: live counters: "N evidence objects · M citations · last full run <ts>".
- Right: disclaimer: *"Evidence aggregation, not investment advice."*

---

## 9. Cross-cutting behavior

### Live rescore (the demo moment)
Public page is read-only cache. When a rescore completes (admin-triggered or cron):
1. Sticky mini-gauge pulses → counts to new BTI.
2. A1 needle sweeps; A2 dots flip with a 300ms stagger; A3 sentence crossfades if stage changed.
3. Changed signature lamps pulse once; hero chart drops any newly-fired pin with a 200ms fall-in.
4. D1 polygon morphs; E sparklines append a point.
Everything else stays still — idle calm is what makes the change legible on stage.
- Delivery: frontend **polls** `GET /state` every 2s while `status=running`, 15s when idle. On `run_id` change, diff new vs previous `/state` payload client-side and play the change choreography. Screen 2's trace feed polls `GET /events?since=<last_id>`. No SSE — the DB is the event log, so every run is also replayable via `GET /state?run_id=` (demo fallback).

### Empty / degraded states
- Factor stale (agent failed): factor header shows "stale · <last good ts>" chip; sub-score renders at last good value, dimmed 20%.
- Full cold start: skeletons per section; sections render independently as data arrives (no full-page blocker).

### Performance & scope guards
- All series pre-downsampled server-side (weekly); page ships ≤ ~200KB of JSON.
- No zoom, no pan, no date pickers, no per-user state. One drawer open at a time.
- Charts: Recharts for line/radar/sparklines; gauge + thermometer as bespoke SVG (simple shapes, full styling control).

### Screenshot rule
Sections A+B together must be self-explanatory with zero interaction: gauge, count, sentence, and the two-era chart with pins. Test by screenshotting at 1200×630 (OG-image crop) — this doubles as the social card.

---

## 10. Build order (UI only)

1. Layout shell + top bar + section skeletons (Replit Agent scaffold).
2. Section C signature board with mock JSON — it's the core and pure DOM (no chart lib risk).
3. Section A (gauge SVG + counter + sentence templates).
4. Section B hero chart (hardest chart — budget accordingly), Price view first, Rates toggle second.
5. Section E quant cards (easy, real data early — first "it's alive" moment).
6. Section D radar + thermometer.
7. Rescore choreography via poll-diffing consecutive `/state` payloads.
8. Polish pass: spacing, chips, hover states, OG screenshot check.

Mock-first: build everything against a static `scores.json` + `evidence.json` fixture matching the real schema; swap to live API last.
