"""Pass 2 pipeline: F5 + F1-rates are REAL (quant probes, deterministic math);
F2/F3/F4/F6 remain the paced fake from Pass 1 until Passes 3-5 replace them.

Also owns hero-series assembly: real benchmark files from /data/benchmarks
overlay the fixture's synthetic curves at seed time and on every run.
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
from agents.f2 import B1_STRONG_INPUT, B2_WEAK_INPUT, run_binary_probe, run_tone_probe
from agents.quant import compute_quant

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "data" / "benchmarks"


def _mock() -> bool:
    return os.environ.get("MOCK", "0") == "1"


FAKE_FACTORS = ["f3", "f4", "f6"]  # + f2 when MOCK=1 (see run_pipeline)
FAKE_ENDPOINT = {"f2": "finance_research", "f3": "research", "f4": "finance_research", "f6": "search"}
FAKE_COST = {"f2": 0.11, "f3": 0.05, "f4": 0.11, "f6": 0.01}
FACTOR_NAMES = {"f1": "Liquidity", "f2": "Bellwethers", "f3": "Circular financing",
                "f4": "Insiders", "f5": "Breadth", "f6": "Narrative"}

_run_counter = 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _emit(run_id: str, event_type: str, **kw) -> None:
    await store_mod.STORE.emit(RunEvent(id=0, run_id=run_id, ts=_now(), event_type=event_type, **kw))


def apply_real_hero(state: StatePayload) -> None:
    """Overlay real benchmark series (if fetched) onto the state's hero block."""
    try:
        e99 = json.loads((BENCH / "ixic_1996_2001.json").read_text())
        enow = json.loads((BENCH / "ixic_now.json").read_text())
        meta = json.loads((BENCH / "meta.json").read_text())
    except FileNotFoundError:
        return  # fixture synthetic stays — run scripts/fetch_benchmarks.py
    state.hero.era_1999 = [SeriesPoint(**p) for p in e99]
    state.hero.era_now = [SeriesPoint(**p) for p in enow]
    state.hero.peak_date_1999 = meta["peak_date_1999"]


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


# ----------------------------------------------------------------- real quant
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


def _apply_quant(state: StatePayload, q: dict, run_id: str) -> list[Evidence]:
    """Write quant results into factors, signatures, quant_strip. Deterministic."""
    p, now = q["probes"], _now()

    f5 = next(f for f in state.factors if f.factor == "f5")
    f5.score, f5.state, f5.sub_metrics, f5.cost, f5.as_of = (
        q["f5_score"], "ok", q["f5_sub_metrics"], 0.0, now)

    f1 = next(f for f in state.factors if f.factor == "f1")
    f1.sub_metrics = {**f1.sub_metrics, **q["f1_sub_metrics"]}
    if q["f1_rates_score"] is not None:
        f1.score, f1.state, f1.as_of = q["f1_rates_score"], "low_coverage", now
        # low_coverage: rhetoric + futures-implied sub-metrics still missing (Pass 4)

    evidence = _quant_evidence(run_id, q)
    by_probe = {e.probe_id: e.evidence_id for e in evidence}

    top10, gap, dma = (q["f5_sub_metrics"]["top10_weight_pct"],
                       q["f5_sub_metrics"]["spy_minus_rsp_6m_pp"],
                       q["f5_sub_metrics"]["pct_above_200dma"])
    for sig in state.signatures:
        if sig.signature_id == "sig-f5-concentration":
            sig.strong_count = 1 if top10 > 38.0 else 0
            sig.weak_count = 0
            sig.current_reading = f"Top-10 weight {top10}% — " + (
                "above trigger, far above 1999 peak" if top10 > 38 else "below trigger")
            sig.current_source_url = p["top10"]["url"]
            sig.confidence = "high"
            sig.driving_evidence_ids = [by_probe["F5-top10"]]
            _relamp(sig)
        elif sig.signature_id == "sig-f5-breadth":
            fired = gap > 8.0 and dma < 45.0
            sig.no_data_reason = None
            sig.strong_count = 1 if fired else 0
            sig.weak_count = 0 if not fired else sig.weak_count
            sig.lamp = "fired" if fired else "not"
            sig.current_reading = (f"Gap {gap:+.1f}pp, {dma:.0f}% above 200dma — "
                                   + ("divergence extreme" if fired else "no 1999-style divergence"))
            sig.current_source_url = p["gap"]["url"]
            sig.confidence = "high"
            sig.driving_evidence_ids = [by_probe["F5-eqw"], by_probe["F5-200dma"]]
        elif sig.signature_id == "sig-f1-path":
            steep = q["f1_sub_metrics"].get("path_steepness_bp")
            if steep is not None:
                sig.strong_count = 1 if steep > 100 else 0
                sig.weak_count = 0
                sig.current_reading = f"Implied path {steep:+.0f}bp/12m — " + (
                    "above trigger" if steep > 100 else "below trigger")
                sig.current_source_url = p["rates"]["url"]
                sig.confidence = "medium"  # proxy, not futures
                sig.driving_evidence_ids = [by_probe["F1-rates"]]
                _relamp(sig)

    # Section E — real cards
    for card in state.quant_strip:
        if card.card_id == "top10":
            card.value, card.sparkline = top10, []
            card.source, card.as_of = "fmp", str(now.date())
        elif card.card_id == "gap":
            card.value, card.sparkline = gap, p["gap"]["sparkline"]
            card.source, card.as_of = "yfinance", str(now.date())
        elif card.card_id == "200dma":
            card.value, card.sparkline = dma, p["dma200"]["sparkline"]
            card.source, card.as_of = "yfinance", str(now.date())
        elif card.card_id == "tnx":
            card.value, card.sparkline = q["f5_sub_metrics"]["tnx_yield"], p["tnx"]["sparkline"]
            card.source, card.as_of = "yfinance", str(now.date())
    return evidence


# ----------------------------------------------------------------- the run
async def run_pipeline() -> str:
    global _run_counter
    _run_counter += 1
    rng = random.Random(_run_counter)

    prev = await store_mod.STORE.state()
    assert prev is not None, "store must be seeded before rescoring"
    # timestamped to the second: unique across process restarts (a module counter
    # alone collides after restart and silently upserts into an old run's row)
    run_id = f"run-{_now():%m%d-%H%M%S}"

    state = prev.model_copy(deep=True)
    state.run_id, state.status, state.prev_bti = run_id, "running", prev.bti
    state.updated_at = _now()
    apply_real_hero(state)
    await store_mod.STORE.put_state(state)
    bal_before = None if _mock() else await youcom.balance()
    await _emit(run_id, "run.started",
                detail={"factors": ["f1", "f2", "f5"] + FAKE_FACTORS,
                        "mock": _mock(), "balance_before": bal_before})
    total_cost = 0.0

    async def real_quant() -> None:
        for f in ("f1", "f5"):
            await _emit(run_id, "agent.started", factor=f)
        t0 = _now()
        try:
            q = await asyncio.to_thread(compute_quant)
        except Exception as exc:  # stale-not-blank: keep last-good scores
            for f in ("f1", "f5"):
                fr = next(x for x in state.factors if x.factor == f)
                fr.state = "stale"
                await _emit(run_id, "agent.failed", factor=f, detail={"reason": str(exc)[:300]})
            return
        elapsed = int((_now() - t0).total_seconds() * 1000)
        for probe, f in (("F5-top10", "f5"), ("F5-eqw", "f5"), ("F5-200dma", "f5"),
                         ("F5-tnx", "f5"), ("F1-rates", "f1")):
            await _emit(run_id, "agent.tool_call", factor=f, probe_id=probe,
                        endpoint="fmp/yfinance", params_summary="deterministic quant",
                        cost=0.0, elapsed_ms=elapsed // 5, cache_hit=q.get("cache_hit", False))
        rows = _apply_quant(state, q, run_id)
        await store_mod.STORE.put_evidence(run_id, rows)
        await _emit(run_id, "agent.evidence", factor="f5", detail={"count": len(rows)})
        for f in ("f5", "f1"):
            fr = next(x for x in state.factors if x.factor == f)
            await _emit(run_id, "agent.completed", factor=f,
                        detail={"score": fr.score, "state": fr.state})

    async def real_f2() -> None:
        """Pass 3 vertical slice: live binaries + tone through the shared chain.
        f2's composite score stays fixture-valued until Pass 4 (revisions, GPU
        spot, tone scoring) — state=low_coverage says so honestly."""
        nonlocal total_cost
        await _emit(run_id, "agent.started", factor="f2")
        fr = next(x for x in state.factors if x.factor == "f2")
        try:
            b1, b2, tone = await asyncio.gather(
                run_binary_probe(store_mod.STORE, run_id, "F2-B1", B1_STRONG_INPUT, 90),
                run_binary_probe(store_mod.STORE, run_id, "F2-B2", B2_WEAK_INPUT, 30),
                run_tone_probe(store_mod.STORE, run_id, "NVDA"),
            )
        except Exception as exc:
            fr.state = "stale"
            await _emit(run_id, "agent.failed", factor="f2", detail={"reason": str(exc)[:300]})
            return

        for probe_id, r in (("F2-B1", b1), ("F2-B2", b2)):
            total_cost += r["cost"]
            await _emit(run_id, "agent.tool_call", factor="f2", probe_id=probe_id,
                        endpoint="research", cost=r["cost"], elapsed_ms=r["elapsed_ms"],
                        params_summary=f"standard · schema · freshness={r['window']}",
                        cache_hit=r["cache_hit"],
                        detail={"answer": r["answer"], "events": len(r["events"]),
                                "excluded_out_of_window": len(r["excluded"])})
        total_cost += tone["cost"]
        await _emit(run_id, "agent.tool_call", factor="f2", probe_id="F2-tone-NVDA",
                    endpoint="finance_research", cost=tone["cost"],
                    elapsed_ms=tone["elapsed_ms"], cache_hit=tone["cache_hit"],
                    params_summary="deep · FINDING template",
                    detail={"extract_stats": tone["stats"],
                            "raw_md_head": tone["raw_md_head"]})

        rows = b1["evidence"] + b2["evidence"] + tone["evidence"]
        await store_mod.STORE.put_evidence(run_id, rows)
        await _emit(run_id, "agent.evidence", factor="f2", detail={"count": len(rows)})

        strong, weak = b1["strong"] + b2["strong"], b1["weak"] + b2["weak"]
        for sig in state.signatures:
            if sig.signature_id == "sig-f2-guidance":
                sig.strong_count, sig.weak_count = strong, weak
                _relamp(sig)
                sig.confidence = "high" if strong else ("medium" if weak else "high")
                sig.current_reading = (
                    f"{strong} strong / {weak} weak signal events in window" if (strong or weak)
                    else "No guidance cuts or misses found in the universe this window")
                if rows:
                    sig.current_source_url = rows[0].source_url
                sig.driving_evidence_ids = [e.evidence_id for e in b1["evidence"] + b2["evidence"]]
        fr.state = "low_coverage"
        fr.as_of = _now()
        fr.cost = round(b1["cost"] + b2["cost"] + tone["cost"], 4)
        fr.sub_metrics = {**fr.sub_metrics,
                          "binary_strong_events": strong, "binary_weak_events": weak,
                          "tone_findings": tone["stats"]}
        await _emit(run_id, "agent.completed", factor="f2",
                    detail={"score": fr.score, "state": fr.state,
                            "strong": strong, "weak": weak})

    async def fake_factor(f: str) -> None:
        nonlocal total_cost
        await asyncio.sleep(rng.uniform(0.5, 4.0))
        await _emit(run_id, "agent.started", factor=f)
        for i in range(rng.randint(2, 4)):
            elapsed = rng.uniform(2.0, 5.0)
            await asyncio.sleep(elapsed)
            cost = FAKE_COST[f]
            total_cost += cost
            await _emit(run_id, "agent.tool_call", factor=f, probe_id=f"{f}-probe-{i+1}",
                        endpoint=FAKE_ENDPOINT[f], params_summary="FAKE until Pass 3-5",
                        cost=cost, elapsed_ms=int(elapsed * 1000), cache_hit=rng.random() < 0.3)
        await _emit(run_id, "agent.evidence", factor=f, detail={"count": rng.randint(1, 4)})
        fr = next(x for x in state.factors if x.factor == f)
        if fr.score is not None and fr.state != "stale":
            fr.score = round(min(100, max(0, fr.score + rng.uniform(-3, 3))), 1)
            fr.as_of = _now()
        await _emit(run_id, "agent.completed", factor=f, detail={"score": fr.score, "state": fr.state})

    f2_task = fake_factor("f2") if _mock() else real_f2()
    await asyncio.gather(real_quant(), f2_task,
                         *(fake_factor(f) for f in FAKE_FACTORS))

    # fake lamp churn only on fake factors' signatures
    changed: list[str] = []
    for sig in state.signatures:
        if sig.factor in FAKE_FACTORS and sig.lamp in ("watch", "partial") and rng.random() < 0.4:
            sig.weak_count = max(0, sig.weak_count + rng.choice([-1, 1]))
            before = sig.lamp
            _relamp(sig)
            if sig.lamp != before:
                changed.append(sig.signature_id)

    state.bti = compute_bti({fr.factor: fr.score for fr in state.factors})
    state.stage_sentence, state.fired_count = stage_sentence(state.signatures)
    deltas = {fr.factor: (fr.score or 0) - (pf.score or 0)
              for fr, pf in zip(state.factors, prev.factors)}
    top = max(deltas, key=lambda k: abs(deltas[k]))
    state.driven_by = f"Driven by: {FACTOR_NAMES[top]} {deltas[top]:+.1f}"
    state.total_cost = round(total_cost, 2)
    state.status, state.updated_at = "done", _now()

    # fake factors keep fixture evidence rows, re-stamped
    _, fixture_rows = store_mod.load_fixture_payload()
    await store_mod.STORE.put_evidence(run_id, [
        r.model_copy(update={"run_id": run_id,
                             "evidence_id": f"{r.evidence_id}-{run_id}"})
        for r in fixture_rows if r.factor in FAKE_FACTORS
    ])
    await store_mod.STORE.put_state(state)
    bal_after = None if _mock() else await youcom.balance()
    await _emit(run_id, "run.completed",
                detail={"bti": state.bti, "changed_signatures": changed,
                        "cost": state.total_cost, "balance_after": bal_after})
    return run_id
