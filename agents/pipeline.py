"""Pass 4 pipeline: F1 (rates+rhetoric), F2 (binaries+tone+GPU+growth),
F4 (insiders), F5 (quant), F6 (narrative) are REAL. F3 stays the paced fake
until Pass 5 — its factor state says `low_coverage` so nothing pretends.

Reliability rules (agents-README §8): per-agent asyncio.wait_for timeout,
try/except → stale-not-blank, endpoint semaphores in the client, preflight
drops priority-3 probes (F4) under budget pressure. MOCK=1 fakes every
paid factor for UI work.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path

from schema import (Evidence, RunEvent, SeriesPoint, StatePayload,
                    compute_bti, stage_sentence)
from agents import store as store_mod
from agents import youcom
from agents.f1 import f1_score, rhetoric_evidence, run_rhetoric_probe
from agents.f2 import B1_STRONG_INPUT, B2_WEAK_INPUT, run_binary_probe
from agents.f2_full import f2_score, run_gpu_spot, run_growth_probe, run_tone_universe
from agents.f4 import run_insider_probe
from agents.f6 import narrative_evidence, run_narrative_probe
from agents.quant import compute_quant

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "data" / "benchmarks"

FAKE_ENDPOINT = {"f2": "finance_research", "f3": "research", "f4": "finance_research", "f6": "search"}
FAKE_COST = {"f2": 0.11, "f3": 0.05, "f4": 0.11, "f6": 0.01}
FACTOR_NAMES = {"f1": "Liquidity", "f2": "Bellwethers", "f3": "Circular financing",
                "f4": "Insiders", "f5": "Breadth", "f6": "Narrative"}
TIMEOUTS = {"quant": 240, "f1": 240, "f2": 480, "f3": 600, "f4": 360, "f6": 300}
MIN_BALANCE_FOR_P3 = 5.0  # below this, priority-3 probes (F4) are dropped

_run_counter = 0


def _mock() -> bool:
    return os.environ.get("MOCK", "0") == "1"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _emit(run_id: str, event_type: str, **kw) -> None:
    await store_mod.STORE.emit(RunEvent(id=0, run_id=run_id, ts=_now(), event_type=event_type, **kw))


def apply_real_hero(state: StatePayload) -> None:
    try:
        e99 = json.loads((BENCH / "ixic_1996_2001.json").read_text())
        enow = json.loads((BENCH / "ixic_now.json").read_text())
        meta = json.loads((BENCH / "meta.json").read_text())
    except FileNotFoundError:
        return
    state.hero.era_1999 = [SeriesPoint(**p) for p in e99]
    state.hero.era_now = [SeriesPoint(**p) for p in enow]
    state.hero.peak_date_1999 = meta["peak_date_1999"]
    try:  # Rates toggle: fed funds as change (pp) from each cycle's anchor month
        ff = json.loads((BENCH / "fedfunds.json").read_text())
        by_date = {r["date"][:7]: r["value"] for r in ff}

        def cycle(anchor: str, start: str, end: str) -> list[SeriesPoint]:
            base = by_date.get(anchor)
            if base is None:
                return []
            pts = [SeriesPoint(t=r["date"][:10], v=round(r["value"] - base, 2))
                   for r in ff if start <= r["date"][:7] <= end]
            return pts

        state.hero.rates_1999 = cycle("1999-06", "1999-06", "2001-12")
        state.hero.rates_now = cycle("2024-09", "2024-09", "2099-01")
    except FileNotFoundError:
        pass


def refresh_pins(state: StatePayload) -> None:
    """1999 pins from config pin dates; today pins = currently-fired signatures.
    Must run AFTER the factor agents have set final lamps."""
    import yaml as _yaml
    from schema import SignaturePin
    cfg = _yaml.safe_load((ROOT / "config/signatures.yaml").read_text())["signatures"]
    state.hero.pins_1999 = [
        SignaturePin(signature_id=c["id"], date=c["pin_date_1999"], label=c["name"],
                     citation_url=c.get("precedent_citation_url"))
        for c in cfg if c.get("pin_date_1999")]
    today = str(_now().date())
    state.hero.pins_now = [
        SignaturePin(signature_id=s.signature_id, date=today, label=s.name)
        for s in state.signatures if s.lamp == "fired"]


def refresh_signature_config(state: StatePayload) -> None:
    """Re-merge display/threshold fields from config/signatures.yaml into the
    run's signature states. Config is the source of truth for names, stages,
    K values, and 1999 precedents — edits land on the next run, and
    runs.config_version ties the score to the config that produced it."""
    import yaml
    cfg = {s["id"]: s for s in yaml.safe_load(
        (ROOT / "config/signatures.yaml").read_text())["signatures"]}
    for sig in state.signatures:
        c = cfg.get(sig.signature_id)
        if not c:
            continue
        sig.name, sig.stage = c["name"], c["stage"]
        sig.threshold_text, sig.k_weak = c["threshold_text"], c["k_weak"]
        sig.precedent_1999 = c["precedent_1999"]
        sig.precedent_citation_url = c.get("precedent_citation_url")


def _relamp(sig) -> None:
    if sig.lamp == "no_data":
        return
    if sig.strong_count >= 1:
        sig.lamp = "fired"
    elif sig.weak_count >= sig.k_weak:
        sig.lamp = "partial"
    elif sig.weak_count >= 1:
        sig.lamp = "watch"
    else:
        sig.lamp = "not"


def _sig(state: StatePayload, sig_id: str):
    return next(s for s in state.signatures if s.signature_id == sig_id)


def _factor(state: StatePayload, f: str):
    return next(x for x in state.factors if x.factor == f)


# ---------------------------------------------------------------- quant (from Pass 2)
def _quant_evidence(run_id: str, q: dict) -> list[Evidence]:
    p = q["probes"]
    today = str(datetime.now(timezone.utc).date())

    def ev(probe_id, factor, metric, value, unit, quote, src) -> Evidence:
        return Evidence(
            evidence_id=f"ev-{run_id}-{probe_id}", run_id=run_id, factor=factor,
            probe_id=probe_id, window=None, metric=metric, value=value, unit=unit,
            as_of=today, quote=quote, source_url=src["url"], confidence="high",
            provenance={"endpoint": src["source"], "cost_usd": 0.0,
                        "computed": "deterministic — no LLM"})

    return [
        ev("F5-top10", "f5", "top10_weight_pct", p["top10"]["value"], "%",
           f"Top-10 weight computed from {p['top10']['coverage']} constituent market caps.",
           p["top10"]),
        ev("F5-eqw", "f5", "spy_minus_rsp_6m_pp", p["gap"]["value"], "pp",
           "SPY minus RSP trailing 6-month total return gap.", p["gap"]),
        ev("F5-200dma", "f5", "pct_above_200dma", p["dma200"]["value"], "%",
           f"Share of {p['dma200']['coverage']} S&P constituents above their 200-day average.",
           p["dma200"]),
        ev("F5-tnx", "f5", "tnx_yield", p["tnx"]["value"], "%",
           "CBOE 10-year Treasury yield index, latest close.", p["tnx"]),
        ev("F1-rates", "f1", "path_steepness_bp", p["rates"]["steepness_bp"], "bp",
           f"1Y treasury {p['rates']['year1']}% minus EFFR {p['rates']['effr']}% — "
           "futures-free proxy for the 12-month implied path.", p["rates"]),
    ]


def _apply_f5(state: StatePayload, q: dict, run_id: str, evidence: list[Evidence]) -> None:
    p, now = q["probes"], _now()
    f5 = _factor(state, "f5")
    f5.score, f5.state, f5.sub_metrics, f5.cost, f5.as_of = (
        q["f5_score"], "ok", q["f5_sub_metrics"], 0.0, now)
    by_probe = {e.probe_id: e.evidence_id for e in evidence}
    top10, gap, dma = (q["f5_sub_metrics"]["top10_weight_pct"],
                       q["f5_sub_metrics"]["spy_minus_rsp_6m_pp"],
                       q["f5_sub_metrics"]["pct_above_200dma"])

    sig = _sig(state, "sig-f5-concentration")
    sig.strong_count, sig.weak_count = (1 if top10 > 38.0 else 0), 0
    sig.current_reading = f"Top-10 weight {top10}% — " + (
        "above trigger, far above 1999 peak" if top10 > 38 else "below trigger")
    sig.current_source_url, sig.confidence = p["top10"]["url"], "high"
    sig.driving_evidence_ids = [by_probe["F5-top10"]]
    _relamp(sig)

    sig = _sig(state, "sig-f5-breadth")
    fired = gap > 8.0 and dma < 45.0
    sig.no_data_reason = None
    sig.strong_count, sig.weak_count = (1 if fired else 0), 0
    sig.lamp = "fired" if fired else "not"
    sig.current_reading = (f"Gap {gap:+.1f}pp, {dma:.0f}% above 200dma — "
                           + ("divergence extreme" if fired else "no 1999-style divergence"))
    sig.current_source_url, sig.confidence = p["gap"]["url"], "high"
    sig.driving_evidence_ids = [by_probe["F5-eqw"], by_probe["F5-200dma"]]

    for card in state.quant_strip:
        if card.card_id == "top10":
            card.value, card.sparkline, card.source, card.as_of = top10, [], "fmp", str(now.date())
        elif card.card_id == "gap":
            card.value, card.sparkline, card.source, card.as_of = gap, p["gap"]["sparkline"], "yfinance", str(now.date())
        elif card.card_id == "200dma":
            card.value, card.sparkline, card.source, card.as_of = dma, p["dma200"]["sparkline"], "yfinance", str(now.date())
        elif card.card_id == "tnx":
            card.value, card.sparkline, card.source, card.as_of = (
                q["f5_sub_metrics"]["tnx_yield"], p["tnx"]["sparkline"], "yfinance", str(now.date()))


# ---------------------------------------------------------------- the run
async def run_pipeline() -> str:
    global _run_counter
    _run_counter += 1
    rng = random.Random(_run_counter)

    prev = await store_mod.STORE.state()
    assert prev is not None, "store must be seeded before rescoring"
    run_id = f"run-{_now():%m%d-%H%M%S}"

    state = prev.model_copy(deep=True)
    state.run_id, state.status, state.prev_bti = run_id, "running", prev.bti
    state.updated_at = _now()
    apply_real_hero(state)
    refresh_signature_config(state)
    try:  # config_version = git SHA of /config — the Forge audit join key (§10)
        import subprocess
        sha = subprocess.run(["git", "log", "-1", "--format=%h", "--", "config/"],
                             capture_output=True, text=True, cwd=ROOT).stdout.strip()
        # Render's runtime image is not a git checkout, so fall back to the deploy
        # commit Render injects. "dev" would silently break the Forge audit join.
        state.config_version = sha or os.environ.get("RENDER_GIT_COMMIT", "")[:7] or "dev"
    except Exception:
        pass
    await store_mod.STORE.put_state(state)

    bal_before = None if _mock() else await youcom.balance()
    drop_p3 = (bal_before is not None and bal_before < MIN_BALANCE_FOR_P3)
    await _emit(run_id, "run.started",
                detail={"mock": _mock(), "balance_before": bal_before,
                        "priority3_dropped": drop_p3})
    total_cost = 0.0
    quant_result: dict = {}

    async def guard(factor_names: list[str], label: str, coro) -> None:
        """Timeout + stale-not-blank wrapper around one factor agent."""
        try:
            await asyncio.wait_for(coro, TIMEOUTS[label])
        except Exception as exc:
            for f in factor_names:
                _factor(state, f).state = "stale"
                await _emit(run_id, "agent.failed", factor=f,
                            detail={"reason": f"{type(exc).__name__}: {str(exc)[:250]}"})

    # ---- F5 + F1 rates (free, deterministic) --------------------------------
    async def real_quant() -> None:
        nonlocal quant_result
        for f in ("f1", "f5"):
            await _emit(run_id, "agent.started", factor=f)
        q = await asyncio.to_thread(compute_quant)
        quant_result = q
        rows = _quant_evidence(run_id, q)
        _apply_f5(state, q, run_id, rows)
        await store_mod.STORE.put_evidence(run_id, rows)
        for probe, f in (("F5-top10", "f5"), ("F5-eqw", "f5"), ("F5-200dma", "f5"),
                         ("F5-tnx", "f5"), ("F1-rates", "f1")):
            await _emit(run_id, "agent.tool_call", factor=f, probe_id=probe,
                        endpoint="fmp/yfinance", params_summary="deterministic quant",
                        cost=0.0, elapsed_ms=0, cache_hit=q.get("cache_hit", False))
        await _emit(run_id, "agent.completed", factor="f5",
                    detail={"score": _factor(state, "f5").score, "state": "ok"})

    # ---- F1 rhetoric + assembly ---------------------------------------------
    async def real_f1() -> None:
        nonlocal total_cost
        r = await run_rhetoric_probe(store_mod.STORE, run_id)
        total_cost += r["cost"]
        await _emit(run_id, "agent.tool_call", factor="f1", probe_id="F1-rhetoric",
                    endpoint="search", cost=r["cost"], elapsed_ms=r.get("elapsed_ms", 0),
                    params_summary="include_domains=federalreserve.gov · livecrawl=web",
                    cache_hit=r.get("cache_hit", False),
                    detail={"speeches_scored": r["n"], "delta": r["delta"]})
        rows = rhetoric_evidence(run_id, r)
        await store_mod.STORE.put_evidence(run_id, rows)
        await _emit(run_id, "agent.evidence", factor="f1", detail={"count": len(rows)})

        steep = (quant_result.get("f1_sub_metrics") or {}).get("path_steepness_bp")
        score, detail = f1_score(steep, r["delta"])
        f1 = _factor(state, "f1")
        f1.score = score if score is not None else f1.score
        f1.state = "low_coverage"  # P(hike)/time-to-tightening/real-rate: no source
        f1.sub_metrics = {**f1.sub_metrics, **detail,
                          "no_data": ["p_hike_next2 (futures)", "time_to_tightening (futures)",
                                      "real_rate (TIPS)"]}
        f1.cost, f1.as_of = r["cost"], _now()

        sig = _sig(state, "sig-f1-rhetoric")
        if r["delta"] is not None:
            sig.strong_count = 1 if r["delta"] > 0.4 else 0
            sig.weak_count = 1 if 0.15 < r["delta"] <= 0.4 else 0
            _relamp(sig)
            sig.current_reading = (f"Rhetoric delta {r['delta']:+.2f} over last "
                                   f"{r['n']} speeches — "
                                   + ("hawkish shift" if r["delta"] > 0.4 else
                                      "drifting hawkish" if r["delta"] > 0.15 else "no hawkish shift"))
            sig.current_source_url = rows[0].source_url if rows else None
            sig.confidence = "medium"
            sig.driving_evidence_ids = [e.evidence_id for e in rows]
        sigp = _sig(state, "sig-f1-path")
        if steep is not None:
            sigp.strong_count = 1 if steep > 100 else 0
            sigp.weak_count = 0
            _relamp(sigp)
            sigp.current_reading = f"Implied path {steep:+.0f}bp/12m — " + (
                "above trigger" if steep > 100 else "below trigger")
            sigp.confidence = "medium"
        await _emit(run_id, "agent.completed", factor="f1",
                    detail={"score": f1.score, "state": f1.state})

    # ---- F2 full --------------------------------------------------------------
    async def real_f2() -> None:
        nonlocal total_cost
        await _emit(run_id, "agent.started", factor="f2")
        f2 = _factor(state, "f2")
        b1, b2, tone, gpu, growth = await asyncio.gather(
            run_binary_probe(store_mod.STORE, run_id, "F2-B1", B1_STRONG_INPUT, 90),
            run_binary_probe(store_mod.STORE, run_id, "F2-B2", B2_WEAK_INPUT, 30),
            run_tone_universe(store_mod.STORE, run_id),
            run_gpu_spot(store_mod.STORE, run_id),
            run_growth_probe(store_mod.STORE, run_id),
        )
        for probe_id, r, endpoint in (("F2-B1", b1, "research"), ("F2-B2", b2, "research"),
                                      ("F2-tone×4", tone, "finance_research"),
                                      ("F2-gpu-spot", gpu, "search"),
                                      ("F2-growth", growth, "finance_research")):
            total_cost += r["cost"]
            await _emit(run_id, "agent.tool_call", factor="f2", probe_id=probe_id,
                        endpoint=endpoint, cost=r["cost"],
                        elapsed_ms=r.get("elapsed_ms", 0),
                        cache_hit=r.get("cache_hit", False),
                        detail={k: v for k, v in r.items()
                                if k in ("answer", "window", "median_tone", "change_30d",
                                         "median_growth_delta_pp", "stats")})
        rows = (b1["evidence"] + b2["evidence"] + tone["evidence"]
                + gpu["evidence"] + growth["evidence"])
        await store_mod.STORE.put_evidence(run_id, rows)
        await _emit(run_id, "agent.evidence", factor="f2", detail={"count": len(rows)})

        score, detail = f2_score(growth["median_growth_delta_pp"],
                                 gpu["change_30d"], tone["median_tone"])
        f2.score = score if score is not None else f2.score
        f2.state = "low_coverage"  # revision momentum: no point-in-time source
        f2.sub_metrics = {**detail,
                          "binary_strong": b1["strong"] + b2["strong"],
                          "binary_weak": b1["weak"] + b2["weak"],
                          "tone_per_ticker": tone["per_ticker"],
                          "gpu_spot_usd_hr": gpu["sample"].get("median_usd_hr"),
                          "no_data": ["revision_momentum (point-in-time consensus)"]}
        f2.cost = round(sum(r["cost"] for r in (b1, b2, tone, gpu, growth)), 4)
        f2.as_of = _now()

        strong, weak = b1["strong"] + b2["strong"], b1["weak"] + b2["weak"]
        sig = _sig(state, "sig-f2-guidance")
        sig.strong_count, sig.weak_count = strong, weak
        _relamp(sig)
        sig.current_reading = (f"{strong} strong / {weak} weak signal events in window"
                               if (strong or weak) else
                               "No guidance cuts or misses in the universe this window")
        if b1["evidence"] or b2["evidence"]:
            sig.current_source_url = (b1["evidence"] + b2["evidence"])[0].source_url
        sig.driving_evidence_ids = [e.evidence_id for e in b1["evidence"] + b2["evidence"]]
        sig.confidence = "high" if strong else "medium"

        sig = _sig(state, "sig-f2-gpu")
        if gpu["change_30d"] is not None:
            sig.no_data_reason = None
            sig.weak_count = 1 if gpu["change_30d"] < -15 else 0
            sig.strong_count = 0
            _relamp(sig)
            sig.current_reading = (f"H100 spot ${gpu['sample']['median_usd_hr']}/hr, "
                                   f"{gpu['change_30d']:+.1f}% over 30d")
            sig.confidence = "low"
        elif gpu["sample"].get("median_usd_hr"):
            sig.lamp = "no_data"
            sig.strong_count = sig.weak_count = 0
            sig.current_reading = f"H100 spot ${gpu['sample']['median_usd_hr']}/hr — first sample stored"
            sig.no_data_reason = ("30d delta needs a prior sample; it ages in from our own "
                                  "stored history, not model memory")
        if gpu["evidence"]:
            sig.driving_evidence_ids = [e.evidence_id for e in gpu["evidence"]]
            sig.current_source_url = gpu["evidence"][0].source_url

        sig = _sig(state, "sig-f2-revisions")
        sig.lamp = "no_data"
        sig.strong_count = sig.weak_count = 0
        sig.current_reading = "Not measurable from allowed sources"
        sig.no_data_reason = ("median NTM revision needs point-in-time consensus history — "
                              "not available via You.com/FMP/yfinance")
        await _emit(run_id, "agent.completed", factor="f2",
                    detail={"score": f2.score, "state": f2.state, "strong": strong, "weak": weak})

    # ---- F4 ---------------------------------------------------------------------
    async def real_f4() -> None:
        nonlocal total_cost
        await _emit(run_id, "agent.started", factor="f4")
        f4 = _factor(state, "f4")
        if drop_p3:
            f4.state = "low_coverage"
            await _emit(run_id, "agent.completed", factor="f4",
                        detail={"skipped": "priority-3 dropped at preflight (budget)"})
            return
        r = await run_insider_probe(store_mod.STORE, run_id)
        total_cost += r["cost"]
        await _emit(run_id, "agent.tool_call", factor="f4", probe_id="F4-insider",
                    endpoint="finance_research", cost=r["cost"],
                    elapsed_ms=r.get("elapsed_ms", 0), cache_hit=r.get("cache_hit", False),
                    detail={"mega": r["mega_count"], "scheduled_10b5_1": r["scheduled_count"],
                            "stats": r["stats"]})
        await store_mod.STORE.put_evidence(run_id, r["evidence"])
        await _emit(run_id, "agent.evidence", factor="f4", detail={"count": len(r["evidence"])})
        f4.score, f4.state = r["score"], "low_coverage"  # ratio/overhang: no clean source
        f4.sub_metrics = {"mega_sale_count_90d": r["mega_count"],
                          "scheduled_10b5_1": r["scheduled_count"],
                          "effective_count": r["effective_count"],
                          "no_data": ["sell_buy_ratio (Form-4 aggregate feed)",
                                      "overhang_pct_adv (ADV data)"]}
        f4.cost, f4.as_of = r["cost"], _now()

        sig = _sig(state, "sig-f4-megasale")
        sig.strong_count = 1 if r["effective_count"] >= 4 else 0
        sig.weak_count = int(r["effective_count"]) if r["effective_count"] < 4 else 0
        _relamp(sig)
        sig.current_reading = (f"{r['mega_count']} mega-sales + {r['scheduled_count']} scheduled "
                               f"programs (90d) — effective {r['effective_count']:.1f} vs trigger 4")
        sig.confidence = "medium"
        if r["evidence"]:
            sig.current_source_url = r["evidence"][0].source_url
            sig.driving_evidence_ids = [e.evidence_id for e in r["evidence"]]
        await _emit(run_id, "agent.completed", factor="f4",
                    detail={"score": f4.score, "state": f4.state})

    # ---- F6 ----------------------------------------------------------------------
    async def real_f6() -> None:
        nonlocal total_cost
        await _emit(run_id, "agent.started", factor="f6")
        r = await run_narrative_probe(store_mod.STORE, run_id)
        total_cost += r["cost"]
        await _emit(run_id, "agent.tool_call", factor="f6", probe_id="F6-narrative",
                    endpoint="search", cost=r["cost"], cache_hit=r.get("cache_hit", False),
                    params_summary="freshness=week · count=50 · livecrawl=news",
                    detail={"density": r["density"], "n": r["n_articles"]})
        rows = narrative_evidence(run_id, r)
        await store_mod.STORE.put_evidence(run_id, rows)
        f6 = _factor(state, "f6")
        f6.score, f6.cost, f6.as_of = r["score"], r["cost"], _now()
        # density over a thin sample is noise — say so instead of shouting 100
        f6.state = "ok" if r["n_articles"] >= 20 else "low_coverage"
        f6.sub_metrics = {"hype_density": r["density"], "baseline_1999": r["baseline_1999"],
                          "articles_sampled": r["n_articles"]}
        state.thermometer = {"density": r["density"], "baseline_1999": r["baseline_1999"],
                             "score": r["score"], "phrases": r["phrases"],
                             "baseline_citation": r["baseline_citation"]}
        await _emit(run_id, "agent.completed", factor="f6",
                    detail={"score": r["score"], "state": "ok"})

    # ---- F3 fake until Pass 5 ------------------------------------------------------
    async def fake_factor(f: str) -> None:
        nonlocal total_cost
        await asyncio.sleep(rng.uniform(0.5, 4.0))
        await _emit(run_id, "agent.started", factor=f)
        for i in range(rng.randint(2, 4)):
            elapsed = rng.uniform(2.0, 5.0)
            await asyncio.sleep(elapsed)
            total_cost += FAKE_COST[f]
            await _emit(run_id, "agent.tool_call", factor=f, probe_id=f"{f}-probe-{i+1}",
                        endpoint=FAKE_ENDPOINT[f], params_summary="FAKE until Pass 5",
                        cost=FAKE_COST[f], elapsed_ms=int(elapsed * 1000),
                        cache_hit=rng.random() < 0.3)
        fr = _factor(state, f)
        if fr.score is not None and fr.state != "stale":
            fr.score = round(min(100, max(0, fr.score + rng.uniform(-3, 3))), 1)
            fr.as_of = _now()
        fr.state = "low_coverage"  # fake — flagged until Pass 5
        await _emit(run_id, "agent.completed", factor=f, detail={"score": fr.score, "state": fr.state})

    async def real_f3() -> None:
        nonlocal total_cost
        from agents.f3_run import run_f3

        async def emit(event_type: str, **kw) -> None:
            await _emit(run_id, event_type, **kw)

        await _emit(run_id, "agent.started", factor="f3")
        cost = await run_f3(store_mod.STORE, state, run_id, emit)
        total_cost += cost
        f3 = _factor(state, "f3")
        await _emit(run_id, "agent.completed", factor="f3",
                    detail={"score": f3.score, "state": f3.state})

    if _mock():
        await asyncio.gather(guard(["f1", "f5"], "quant", real_quant()),
                             *(fake_factor(f) for f in ("f2", "f3", "f4", "f6")))
    else:
        await guard(["f1", "f5"], "quant", real_quant())  # f1 assembly needs quant first
        await asyncio.gather(
            guard(["f1"], "f1", real_f1()),
            guard(["f2"], "f2", real_f2()),
            guard(["f3"], "f3", real_f3()),
            guard(["f4"], "f4", real_f4()),
            guard(["f6"], "f6", real_f6()),
        )

    state.bti = compute_bti({fr.factor: fr.score for fr in state.factors})
    state.stage_sentence, state.fired_count = stage_sentence(state.signatures)
    deltas = {fr.factor: (fr.score or 0) - (pf.score or 0)
              for fr, pf in zip(state.factors, prev.factors)}
    top = max(deltas, key=lambda k: abs(deltas[k]))
    state.driven_by = f"Driven by: {FACTOR_NAMES[top]} {deltas[top]:+.1f}"
    state.total_cost = round(total_cost, 2)
    state.status, state.updated_at = "done", _now()
    refresh_pins(state)
    all_rows = []
    for f in ("f1", "f2", "f3", "f4", "f5", "f6"):
        all_rows.extend(await store_mod.STORE.evidence_for(f, run_id))
    state.evidence_count = len(all_rows)
    state.citation_count = len({r.source_url for r in all_rows if r.source_url})

    await store_mod.STORE.put_state(state)
    bal_after = None if _mock() else await youcom.balance()
    await _emit(run_id, "run.completed",
                detail={"bti": state.bti, "cost": state.total_cost,
                        "balance_after": bal_after})
    return run_id
