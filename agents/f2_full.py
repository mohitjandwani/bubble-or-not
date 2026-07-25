"""F2 Bellwethers — Pass 4 completion on top of f2.py's binaries.

- Guidance tone × N tickers (Pattern B → shared extract() → Haiku §5.4 scorer → median)
- GPU spot (SEARCH → Haiku price extraction → 30d delta vs our own stored samples)
- Growth deceleration (Pattern B, one call for the universe)
- Estimate-revision momentum: point-in-time consensus history has NO allowed
  source → the signature renders no-data (honesty is the feature).

F2 score (methodology §F2, renormalized over available):
  0.25·(1−norm(growth_delta,−20,+10)) + 0.20·(1−norm(gpu_30d,−25,+10)) + 0.20·(1−tone/10)
  (0.35 revision momentum weight excluded until a point-in-time source exists)
"""
from __future__ import annotations

import asyncio
import statistics
from datetime import date, timedelta

from schema import Evidence
from agents import youcom
from agents.extract import FINDING_TEMPLATE, extract
from agents.f2 import run_tone_probe
from agents.llm import TONE_SYSTEM, haiku_json
from agents.quant import norm

TONE_UNIVERSE = ["NVDA", "MSFT", "CRWV", "META"]  # config-expandable to all 8

GROWTH_EVENTS = ["growth_decelerating", "growth_accelerating", "growth_flat", "none_found"]
GROWTH_INPUT = (
    "For each of NVDA, MSFT, META, GOOGL, AVGO, AMZN, ORCL, CRWV: compare expected "
    "next-twelve-months revenue growth (consensus) with realized last-twelve-months "
    "revenue growth. One finding per company: EVENT growth_decelerating if NTM growth "
    "is below LTM growth, growth_accelerating if above, growth_flat if within 1pp. "
    "VALUE = the difference in percentage points (NTM minus LTM)."
    + FINDING_TEMPLATE.format(enum=" | ".join(GROWTH_EVENTS))
)


async def run_tone_universe(store, run_id: str) -> dict:
    """Tone probes for the universe (semaphore-limited upstream), then the
    Haiku 0-10 confidence rubric over each ticker's extracted QUOTE fields."""
    results = await asyncio.gather(
        *(run_tone_probe(store, run_id, t) for t in TONE_UNIVERSE),
        return_exceptions=True)
    per_ticker: dict[str, dict] = {}
    evidence: list[Evidence] = []
    cost = 0.0
    for ticker, r in zip(TONE_UNIVERSE, results):
        if isinstance(r, Exception):
            per_ticker[ticker] = {"error": str(r)[:200]}
            continue
        cost += r["cost"]
        evidence.extend(r["evidence"])
        quotes = "\n".join(f"- {e.quote}" for e in r["evidence"]
                           if e.quote and e.metric != "extract_failed")
        if not quotes:
            per_ticker[ticker] = {"score": None}
            continue
        try:
            tone = await haiku_json(TONE_SYSTEM, f"Guidance language for {ticker}:\n{quotes}")
            per_ticker[ticker] = {"score": int(tone["score"]),
                                  "hedging": tone.get("hedging_phrases", [])[:3]}
        except Exception as exc:
            per_ticker[ticker] = {"error": str(exc)[:120]}
    scores = [v["score"] for v in per_ticker.values() if v.get("score") is not None]
    return {"median_tone": statistics.median(scores) if scores else None,
            "per_ticker": per_ticker, "evidence": evidence, "cost": cost}


async def run_gpu_spot(store, run_id: str, ttl_hours: float = 12.0) -> dict:
    """SEARCH pattern: current H100 spot $/GPU-hr via Haiku extraction; the 30d
    delta comes from OUR stored samples (probe_cache keyed by date) once ≥2
    samples exist ≥20 days apart — never from a model's memory of prices."""
    probe_id = "F2-gpu-spot"
    today = str(date.today())
    cached = await store.cache_get(probe_id, today, ttl_hours)
    if cached is not None:
        sample, resp_cost, cache_hit = cached, 0.0, True
    else:
        resp = await youcom.search(
            "H100 GPU rental price per hour cloud marketplace spot",
            count=15, freshness="month", livecrawl="web")
        items = (resp["results"].get("web") or [])[:8]
        corpus = "\n\n".join(
            f"URL: {i.get('url')}\n{(i.get('markdown') or ' '.join(i.get('snippets') or []))[:1500]}"
            for i in items)
        extraction = await haiku_json(
            "Extract current H100 GPU hourly rental prices in USD from the text. "
            "Use ONLY prices stated in the text. Output JSON: "
            '{"prices": [{"usd_per_hour": float, "provider": str, "url": str}], '
            '"median": float|null}',
            corpus[:20000])
        prices = [p["usd_per_hour"] for p in extraction.get("prices", [])
                  if isinstance(p.get("usd_per_hour"), (int, float)) and 0.3 < p["usd_per_hour"] < 30]
        sample = {"median_usd_hr": round(statistics.median(prices), 2) if prices else None,
                  "n_prices": len(prices), "date": today,
                  "prices": extraction.get("prices", [])[:6]}
        await store.cache_put(probe_id, today, sample)
        resp_cost, cache_hit = resp["cost_usd"], False

    # 30d delta vs our own history
    change_30d = None
    if sample.get("median_usd_hr"):
        for back in range(20, 45):
            old_day = str(date.today() - timedelta(days=back))
            old = await store.cache_get(probe_id, old_day, ttl_hours=24 * 60)
            if old and old.get("median_usd_hr"):
                change_30d = round((sample["median_usd_hr"] / old["median_usd_hr"] - 1) * 100, 1)
                break

    evidence = []
    if sample.get("median_usd_hr") is not None:
        evidence.append(Evidence(
            evidence_id=f"ev-{run_id}-F2-gpu", run_id=run_id, factor="f2",
            probe_id=probe_id, window=today, metric="h100_spot_usd_hr",
            value=sample["median_usd_hr"], unit="$/hr", as_of=today,
            quote=f"Median of {sample['n_prices']} listed H100 hourly prices across marketplace pages.",
            source_url=(sample["prices"][0].get("url") if sample.get("prices") else None),
            confidence="low",  # scrappy sources by design — flagged in docs
            provenance={"endpoint": "search", "livecrawl": "web",
                        "extractor": "haiku price extraction",
                        "delta_30d_pct": change_30d,
                        "delta_basis": "own stored samples" if change_30d is not None
                                       else "no prior sample yet"}))
    return {"sample": sample, "change_30d": change_30d, "evidence": evidence,
            "cost": resp_cost, "cache_hit": cache_hit}


async def run_growth_probe(store, run_id: str, ttl_hours: float = 24.0) -> dict:
    probe_id = "F2-growth"
    window = str(date.today())
    cached = await store.cache_get(probe_id, window, ttl_hours)
    if cached is not None:
        resp, cache_hit = cached, True
    else:
        resp = await youcom.finance_research(GROWTH_INPUT, effort="deep")
        await store.cache_put(probe_id, window, resp)
        cache_hit = False
    result = extract(resp["content"], resp["sources"], GROWTH_EVENTS)
    import re as _re
    deltas, evidence = [], []
    for i, f in enumerate(result.findings):
        # VALUE like "-6.2 percentage points" → first float, else None
        m = _re.search(r"-?\d+(?:\.\d+)?", f.value or "")
        value_num = float(m.group(0)) if m else None
        if value_num is not None:
            deltas.append(value_num)
        evidence.append(Evidence(
            evidence_id=f"ev-{run_id}-F2-growth-{i}", run_id=run_id, factor="f2",
            probe_id=probe_id, window=window, metric=f.event,
            value=value_num, unit="pp",
            as_of=f.date, quote=f.quote, source_url=f.source_url, confidence="medium",
            provenance={"endpoint": "finance_research", "effort": "deep",
                        "cost_usd": 0.0 if cache_hit else resp["cost_usd"],
                        "cache_hit": cache_hit, "extract_stats": result.stats}))
    return {"median_growth_delta_pp": statistics.median(deltas) if deltas else None,
            "n": len(deltas), "evidence": evidence, "stats": result.stats,
            "cost": 0.0 if cache_hit else resp["cost_usd"], "cache_hit": cache_hit}


def f2_score(growth_delta_pp: float | None, gpu_30d_pct: float | None,
             median_tone: float | None) -> tuple[float | None, dict]:
    """Renormalized §F2 formula; 0.35 revision-momentum weight excluded (no
    point-in-time source). Higher = deteriorating forward picture."""
    parts, detail = [], {}
    if growth_delta_pp is not None:
        parts.append((0.25, 1 - norm(growth_delta_pp, -20, 10)))
        detail["growth_delta_pp"] = growth_delta_pp
    if gpu_30d_pct is not None:
        parts.append((0.20, 1 - norm(gpu_30d_pct, -25, 10)))
        detail["gpu_spot_30d_pct"] = gpu_30d_pct
    if median_tone is not None:
        parts.append((0.20, 1 - median_tone / 10))
        detail["median_guidance_tone"] = median_tone
    if not parts:
        return None, detail
    w = sum(p[0] for p in parts)
    return round(100 * sum(wi * v for wi, v in parts) / w, 1), detail
