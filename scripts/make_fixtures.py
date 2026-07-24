"""Generate data/fixtures/{state,evidence}.json — a plausible full system state
matching schema.py exactly. Deterministic (no randomness): the same fixtures every run.

The fixture deliberately exercises every UI state the spec demands:
fired / partial / watch / not / no_data lamps, a stale factor, low/med/high
confidence, a conflicting-evidence pair, both hero eras, thermometer phrases.
"""
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from schema import (  # noqa: E402
    Evidence, FactorResult, HeroSeries, QuantCard, SeriesPoint, SignaturePin,
    SignatureState, StatePayload, compute_bti, stage_sentence,
)

NOW = datetime(2026, 7, 24, 9, 30, tzinfo=timezone.utc)
RUN_ID = "run-fixture-0001"

cfg_sig = yaml.safe_load((ROOT / "config/signatures.yaml").read_text())["signatures"]
cfg_w = yaml.safe_load((ROOT / "config/weights.yaml").read_text())

# ---------------------------------------------------------------- factor results
FACTOR_FIXTURES = {
    "f1": dict(score=64.0, state="ok", sub_metrics={
        "path_steepness_bp": 85, "p_hike_next2": 0.42, "rhetoric_delta": 0.3,
        "time_to_tightening_d": 112, "real_rate_pct": 1.9}),
    "f2": dict(score=41.0, state="ok", sub_metrics={
        "revision_momentum_pct": 1.8, "growth_delta_pp": -6.0,
        "gpu_spot_30d_pct": -9.0, "guidance_tone": 6.4, "misses_last_q": 1}),
    "f3": dict(score=57.0, state="ok", sub_metrics={
        "circularity_ratio_pct": 1.4, "cmi_stage1": -0.2, "cmi_stage2": 0.6,
        "verified_edges": 9, "announced_only_edges": 4,
        "revenue_quality": {"openai": 0.62, "anthropic": 0.71}}),
    "f4": dict(score=52.0, state="stale", sub_metrics={  # exercises the stale chip
        "mega_sale_count_90d": 3, "sell_buy_ratio_vs_median": 2.1}),
    "f5": dict(score=71.0, state="ok", sub_metrics={
        "top10_weight_pct": 39.4, "spy_minus_rsp_6m_pp": 7.2,
        "pct_above_200dma": 48.0, "tnx_yield": 4.70}),
    "f6": dict(score=66.0, state="ok", sub_metrics={
        "hype_density": 0.31, "baseline_1999": 0.47, "articles_sampled": 50}),
}

FACTOR_COSTS = {"f1": 0.02, "f2": 0.9, "f3": 0.7, "f4": 0.22, "f5": 0.0, "f6": 0.06}
factors = [
    FactorResult(factor=f, as_of=NOW, cost=FACTOR_COSTS[f], **FACTOR_FIXTURES[f])
    for f in ["f1", "f2", "f3", "f4", "f5", "f6"]
]

# ---------------------------------------------------------------- signatures
# Chosen to exercise every lamp state; counts obey the lamp rule deterministically.
SIG_STATES = {
    "sig-f1-path":          dict(lamp="watch",   strong=0, weak=2, conf="high",
        reading="Implied path +85bp/12m — steepening, below trigger"),
    "sig-f1-rhetoric":      dict(lamp="partial", strong=0, weak=3, conf="medium",
        reading="Rhetoric delta +0.30 — hawkish drift across last 5 speeches"),
    "sig-f2-revisions":     dict(lamp="not",     strong=0, weak=0, conf="high",
        reading="Median bellwether NTM revision +1.8% — still positive"),
    "sig-f2-guidance":      dict(lamp="not",     strong=0, weak=0, conf="medium",
        reading="No cuts or withdrawals in the universe this quarter"),
    "sig-f2-gpu":           dict(lamp="watch",   strong=0, weak=1, conf="low",
        reading="H100 spot -9% over 30d — drifting, above trigger"),
    "sig-f3-churn":         dict(lamp="partial", strong=0, weak=4, conf="medium",
        reading="Startup shutdown mentions up 2 consecutive weeks — cluster forming"),
    "sig-f3-drift":         dict(lamp="fired",   strong=1, weak=1, conf="high",
        reading="One lab shifted 'ARR' definition to include committed contracts"),
    "sig-f3-vendor":        dict(lamp="fired",   strong=1, weak=2, conf="medium",
        reading="Circularity Ratio 1.4% of assets — inside the 1999 band"),
    "sig-f3-distress":      dict(lamp="not",     strong=0, weak=0, conf="high",
        reading="No canceled or renegotiated registry-edge orders this window"),
    "sig-f4-megasale":      dict(lamp="watch",   strong=0, weak=2, conf="low",
        reading="3 mega-sale programs in 90d — below the 4-program trigger"),
    "sig-f5-concentration": dict(lamp="fired",   strong=1, weak=0, conf="high",
        reading="Top-10 weight 39.4% — above trigger, far above 1999 peak"),
    "sig-f5-breadth":       dict(lamp="no_data", strong=0, weak=0, conf="low",
        reading="Not measurable from allowed sources",
        no_data="NYSE 52wk high-low internals not available via You.com/FMP/yfinance free tiers"),
}

signatures = []
for s in cfg_sig:
    st = SIG_STATES[s["id"]]
    signatures.append(SignatureState(
        signature_id=s["id"], lamp=st["lamp"], strong_count=st["strong"], weak_count=st["weak"],
        driving_evidence_ids=[f"ev-{s['id']}-1"],
        name=s["name"], factor=s["factor"], stage=s["stage"],
        threshold_text=s["threshold_text"], k_weak=s["k_weak"],
        precedent_1999=s["precedent_1999"], precedent_citation_url=s.get("precedent_citation_url"),
        current_reading=st["reading"], current_source_url="https://example.com/fixture",
        confidence=st["conf"], no_data_reason=st.get("no_data"),
    ))

# ---------------------------------------------------------------- hero series (synthetic until Pass 2)
def curve(n: int, shape: str) -> list[float]:
    out = []
    for i in range(n):
        x = i / (n - 1)
        if shape == "bubble":   # 1996-2001: rise, blowoff, crash
            v = 100 * (1 + 2.2 * x ** 2 + 2.6 * math.exp(-((x - 0.68) ** 2) / 0.008))
            if x > 0.68:
                v *= math.exp(-2.2 * (x - 0.68))
        else:                   # 2023-now: steady climb
            v = 100 * (1 + 1.5 * x ** 1.6)
        out.append(round(v, 1))
    return out


def week_series(start_year: int, n: int, vals: list[float]) -> list[SeriesPoint]:
    pts = []
    for i, v in enumerate(vals):
        y = start_year + (i * 7) // 365
        d = (i * 7) % 365
        pts.append(SeriesPoint(t=f"{y}-{min(12, 1 + d // 31):02d}-{min(28, 1 + d % 28):02d}", v=v))
    return pts[:n]


hero = HeroSeries(
    era_1999=week_series(1996, 310, curve(310, "bubble")),
    era_now=week_series(2023, 186, curve(186, "climb")),
    pins_1999=[
        SignaturePin(signature_id="sig-f1-path", date="1999-06-30", label="First hike of the cycle"),
        SignaturePin(signature_id="sig-f5-concentration", date="1999-12-15", label="Concentration extreme"),
        SignaturePin(signature_id="sig-f2-revisions", date="2000-01-20", label="Revisions roll over"),
        SignaturePin(signature_id="sig-f4-megasale", date="2000-02-15", label="Insider selling wave"),
    ],
    pins_now=[
        SignaturePin(signature_id="sig-f5-concentration", date="2026-05-10", label="Concentration extreme"),
        SignaturePin(signature_id="sig-f3-vendor", date="2026-06-22", label="Vendor financing material"),
    ],
    peak_date_1999="2000-03-10",
)

# ---------------------------------------------------------------- quant strip
quant_strip = [
    QuantCard(card_id="top10", label="Top-10 S&P 500 weight", value=39.4, unit="%",
              sparkline=[35.1, 35.8, 36.2, 36.0, 36.9, 37.4, 37.8, 38.1, 38.6, 38.9, 39.1, 39.4],
              threshold=38.0, threshold_label="trigger", source="fmp", as_of="2026-07-23"),
    QuantCard(card_id="gap", label="Cap vs equal-weight, 6m", value=7.2, unit="pp",
              sparkline=[2.1, 2.8, 3.5, 3.1, 4.2, 4.8, 5.5, 5.9, 6.3, 6.6, 7.0, 7.2],
              threshold=8.0, threshold_label="danger", source="yfinance", as_of="2026-07-23"),
    QuantCard(card_id="200dma", label="% above 200dma", value=48.0, unit="%",
              sparkline=[62, 60, 58, 61, 57, 55, 53, 52, 50, 49, 48, 48],
              threshold=45.0, threshold_label="danger", source="fmp", as_of="2026-07-23"),
    QuantCard(card_id="tnx", label="10Y Treasury yield", value=4.70, unit="%",
              sparkline=[4.2, 4.25, 4.3, 4.28, 4.35, 4.4, 4.38, 4.45, 4.5, 4.55, 4.66, 4.70],
              threshold=None, threshold_label="6-mo change +0.4pp", source="yfinance", as_of="2026-07-23"),
]

# ---------------------------------------------------------------- assemble state
sent, fired_n = stage_sentence(signatures)
state = StatePayload(
    run_id=RUN_ID, status="done", updated_at=NOW,
    bti=compute_bti({f.factor: f.score for f in factors}),
    prev_bti=55.9,
    stage_sentence=sent, driven_by="Driven by: Liquidity +2.1",
    fired_count=fired_n, total_signatures=len(signatures),
    factors=factors, signatures=signatures, quant_strip=quant_strip, hero=hero,
    thermometer={
        "density": 0.31, "baseline_1999": 0.47, "score": 66.0,
        "phrases": [
            {"text": "this time is different", "count": 14, "url": "https://example.com/a"},
            {"text": "new paradigm", "count": 9, "url": "https://example.com/b"},
            {"text": "can't-lose trade", "count": 6, "url": "https://example.com/c"},
        ]},
    danger_thresholds=cfg_w["danger_thresholds"],
    evidence_count=87, citation_count=112, total_cost=2.14,
    config_version="fixture",
)

# ---------------------------------------------------------------- evidence store
def ev(sig_id: str, factor: str, metric: str, value, unit, quote: str, url: str,
       conf: str = "medium", provenance: dict | None = None, suffix: str = "1") -> Evidence:
    return Evidence(
        evidence_id=f"ev-{sig_id}-{suffix}", run_id=RUN_ID, factor=factor, probe_id=f"probe-{sig_id}",
        window="2026-06-24to2026-07-24", metric=metric, value=value, unit=unit,
        as_of="2026-07-20", quote=quote, source_url=url, confidence=conf,
        provenance=provenance or {"endpoint": "research", "effort": "standard",
                                  "params": "freshness=2026-06-24to2026-07-24", "cost_usd": 0.05,
                                  "elapsed_s": 12.4},
    )


evidence: list[Evidence] = [
    ev("sig-f1-path", "f1", "path_steepness_bp", 85, "bp",
       "Futures-implied policy path stands 85bp above the current effective rate at the 12-month horizon.",
       "https://example.com/fixture/rates", "high",
       {"endpoint": "fmp", "params": "federalFunds", "cost_usd": 0, "elapsed_s": 0.4}),
    ev("sig-f1-rhetoric", "f1", "rhetoric_delta", 0.3, "score",
       "Inflation persistence remains the primary risk to the outlook, and further firming may be warranted.",
       "https://www.federalreserve.gov/fixture-speech", "medium"),
    ev("sig-f2-revisions", "f2", "revision_momentum_pct", 1.8, "%",
       "Consensus NTM EPS for the bellwether cohort has risen 1.8% over the trailing window.",
       "https://example.com/fixture/estimates", "high"),
    ev("sig-f2-guidance", "f2", "guidance_tone", 6.4, "score",
       "We are raising our full-year outlook on continued strong data-center demand.",
       "https://example.com/fixture/transcript", "medium"),
    ev("sig-f2-gpu", "f2", "gpu_spot_30d_pct", -9.0, "%",
       "H100 hourly spot pricing has drifted from $2.20 to $2.00 over the past month.",
       "https://example.com/fixture/gpu", "low"),
    ev("sig-f3-churn", "f3", "destruction_count", 4, "events",
       "The startup said it is winding down operations, citing unsustainable API costs.",
       "https://example.com/fixture/shutdown", "medium"),
    ev("sig-f3-drift", "f3", "drift_event", 1, "event",
       "The company now reports 'annualized run-rate revenue including committed contracts'.",
       "https://example.com/fixture/arr", "high"),
    ev("sig-f3-vendor", "f3", "circularity_ratio_pct", 1.4, "%",
       "Purchase commitments to the supplier total $7.8 billion; the supplier holds an equity stake.",
       "https://www.sec.gov/fixture-filing", "medium",
       {"endpoint": "research", "effort": "deep", "params": "include_domains=sec.gov",
        "cost_usd": 0.10, "elapsed_s": 28.0}),
    # deliberate conflicting pair — exercises the disagreement banner:
    ev("sig-f3-vendor", "f3", "circularity_ratio_pct", 2.1, "%",
       "Related-party purchase obligations imply a materially higher circular share.",
       "https://example.com/fixture/conflict", "low", suffix="2"),
    ev("sig-f3-distress", "f3", "distress_events", 0, "events",
       "none_found", "https://example.com/fixture/none", "high"),
    ev("sig-f4-megasale", "f4", "mega_sale_count_90d", 3, "programs",
       "The filing discloses a new 10b5-1 plan covering shares worth approximately $180 million.",
       "https://example.com/fixture/form4", "low"),
    ev("sig-f5-concentration", "f5", "top10_weight_pct", 39.4, "%",
       "Computed from FMP constituent market caps — no LLM in the loop.",
       "https://example.com/fixture/fmp", "high",
       {"endpoint": "fmp", "params": "sp500_constituent+quotes", "cost_usd": 0, "elapsed_s": 1.1}),
]

out = ROOT / "data/fixtures"
out.mkdir(parents=True, exist_ok=True)
(out / "state.json").write_text(state.model_dump_json(indent=2))
(out / "evidence.json").write_text(json.dumps(
    [json.loads(e.model_dump_json()) for e in evidence], indent=2))
print(f"state.json: bti={state.bti} fired={state.fired_count}/{state.total_signatures} "
      f"sigs={len(signatures)} hero_pts={len(hero.era_1999)}+{len(hero.era_now)}")
print(f"evidence.json: {len(evidence)} objects")
