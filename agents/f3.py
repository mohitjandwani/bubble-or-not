"""F3 Circularity — the genuinely agentic factor (spec: f3-circularity-query-battery.md).

Run shape (what a reviewer watches in the trace):
  Stage 1 (usage layer, weekly window):  S1-B1 drift binary · S1-Q1 formation scan
    → Haiku entity extraction → dedup vs registry → FAN OUT S1-Q2 verify ×≤4
    → S1-Q4 destruction canary · S1-Q5 ARR tracker
  Stage 2 (GPU layer, monthly window):   S2-B1 strong binary · S2-Q1 formation scan
    → S2-Q2 counterparty verification (Research deep · sec.gov — the flagship probe)
    → S2-Q5 distress avalanche · S2-Q6 vendor aggregate sanity check

CMI per stage = w_f·clamp(Δformation) − w_d·clamp(Δdestruction) + w_i·Δintensity,
deltas vs the cold-start baseline (scripts/cold_start_f3.py — window-0). No
baseline → no deltas → CMI is no-data, honestly.

F3 sub-score = 50%·norm(CR,0,8%) + 25%·(CMI_s2+1)/2·100 + 25%·(CMI_s1+1)/2·100.
Only counterparty-corroborated edges enter CR — we compute the floor, not the truth.
"""
from __future__ import annotations

import asyncio
import statistics
import re
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import yaml

from schema import Evidence, RegistryEdge, SeriesPoint, WaterfallBar
from agents import youcom
from agents.f2 import run_binary_probe
from agents.llm import haiku_json

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_FILE = ROOT / "data" / "registry" / "edges.yaml"

CMI_W = {"formation": 0.4, "destruction": 0.4, "intensity": 0.2}
VERIFY_FANOUT_CAP = 4

DRIFT_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "boolean"},
        "events": {"type": "array", "items": {"type": "object", "properties": {
            "company": {"type": "string"},
            "event_type": {"type": "string",
                           "enum": ["revenue_definition_change", "guidance_cut",
                                    "reported_miss", "analyst_estimate_cut"]},
            "signal_strength": {"type": "string", "enum": ["strong", "weak"]},
            "date": {"type": ["string", "null"]},
            "magnitude": {"type": ["string", "null"]},
            "quote": {"type": "string"},
            "source_url": {"type": "string"}},
            "required": ["company", "event_type", "signal_strength", "date",
                         "magnitude", "quote", "source_url"],
            "additionalProperties": False}}},
    "required": ["answer", "events"], "additionalProperties": False}

S1_B1_DRIFT = (
    "Answer for the period covered by the search window. Has any AI lab (OpenAI, "
    "Anthropic, xAI, or similar) changed the DEFINITION of a reported revenue metric — "
    "e.g. shifting between recognized revenue, 'annualized run-rate', 'ARR including "
    "committed contracts', or similar redefinitions — in official statements or press? "
    "Use event_type revenue_definition_change for such events. Quote the exact sentence."
)

S2_B1_STRONG = (
    "Answer for the period covered by the search window. Has any of the following occurred?\n"
    "1. NVIDIA or AMD lowered its own guidance or management softened forward demand language.\n"
    "2. Any neocloud (CoreWeave, Nebius, Lambda, ...) reported revenue or operating cash "
    "flow below its own prior guidance, took an impairment, or disclosed a covenant issue.\n"
    "3. Any announced GPU order, datacenter buildout, or capacity contract was canceled, "
    "delayed, or renegotiated by the companies involved.\n"
    "One event object per occurrence with the exact quote; null for unknowns."
)

ENTITY_EXTRACT_SYSTEM = (
    "From these articles, extract announced financing or investment relationships.\n"
    "For each: investor/vendor, recipient/customer, dollar amount if stated (in millions "
    "USD), announcement date, and whether the article states the recipient is also a "
    "customer of the investor.\n"
    "Only include relationships explicitly stated in the text. Output JSON array: "
    '[{"from": str, "to": str, "amount_usd_m": float|null, "date": str|null, '
    '"also_customer": bool, "url": str}]. Use null for anything not stated.')

COUNTERPARTY_SCHEMA = {
    "type": "object",
    "properties": {
        "company": {"type": "string"},
        "findings": {"type": "array", "items": {"type": "object", "properties": {
            "metric": {"type": "string", "enum": [
                "supplier_concentration_pct", "purchase_commitments_usd",
                "customer_concentration_pct", "gpu_collateralized_debt_usd"]},
            "value": {"type": ["number", "null"]},
            "unit": {"type": ["string", "null"]},
            "quote": {"type": ["string", "null"]},
            "source_url": {"type": ["string", "null"]}},
            "required": ["metric", "value", "unit", "quote", "source_url"],
            "additionalProperties": False}}},
    "required": ["company", "findings"], "additionalProperties": False}


def _today() -> str:
    return str(date.today())


def load_registry() -> list[RegistryEdge]:
    data = yaml.safe_load(REGISTRY_FILE.read_text())["edges"]
    return [RegistryEdge(
        edge_id=e["edge_id"], from_entity=e["from_entity"], to_entity=e["to_entity"],
        archetype=e["archetype"], amount_usd_m=e.get("amount_usd_m"),
        announced_date=str(e.get("announced_date") or "") or None,
        status=e.get("status", "announced_only"),
        seed_source_url=e.get("source_url"), note=e.get("note")) for e in data]


# ------------------------------------------------------------------ probes
async def scan_probe(store, probe_id: str, query: str, window_days: int,
                     ttl_hours: float = 12.0, count: int = 30) -> dict:
    """Search + livecrawl news scan; returns raw items + cost. Cached."""
    from datetime import timedelta
    end = date.today()
    window = f"{end - timedelta(days=window_days)}to{end}"
    cached = await store.cache_get(probe_id, window, ttl_hours)
    if cached is not None:
        return {**cached, "cache_hit": True, "cost": 0.0}
    resp = await youcom.search(query, count=count, freshness=window, livecrawl="news")
    items = ((resp["results"].get("news") or []) + (resp["results"].get("web") or []))
    out = {"items": [{"url": i.get("url"), "title": i.get("title"),
                      "page_age": i.get("page_age"),
                      "text": (i.get("markdown") or " ".join(i.get("snippets") or []))[:1200]}
                     for i in items],
           "window": window, "cost": resp["cost_usd"], "cache_hit": False}
    await store.cache_put(probe_id, window, out)
    return out


async def extract_candidate_edges(items: list[dict]) -> list[dict]:
    if not items:
        return []
    corpus = "\n\n".join(f"URL: {i['url']}\nTITLE: {i['title']}\n{i['text']}"
                         for i in items[:20])
    try:
        raw = await haiku_json(ENTITY_EXTRACT_SYSTEM, corpus[:24000], max_tokens=1500)
        return [r for r in raw if isinstance(r, dict) and r.get("from") and r.get("to")]
    except Exception:
        return []


def dedup_vs_registry(candidates: list[dict], registry: list[RegistryEdge]) -> list[dict]:
    """Fuzzy name match: a candidate already in the registry isn't 'formation'."""
    def norm_name(s: str) -> str:
        return re.sub(r"[^a-z]", "", (s or "").lower())[:12]
    known = {(norm_name(e.from_entity), norm_name(e.to_entity)) for e in registry}
    return [c for c in candidates
            if (norm_name(c["from"]), norm_name(c["to"])) not in known]


async def verify_edge(store, candidate: dict, ttl_hours: float = 168.0) -> dict:
    """S1-Q2: is the recipient both investee AND paying customer? (Pattern A)"""
    key = f"S1-Q2-{candidate['from'][:12]}-{candidate['to'][:12]}"
    cached = await store.cache_get(key, "verify", ttl_hours)
    if cached is not None:
        return {**cached, "cache_hit": True, "cost": 0.0}
    schema = {"type": "object", "properties": {
        "is_investee": {"type": "boolean"}, "is_paying_customer": {"type": "boolean"},
        "investment_evidence_url": {"type": ["string", "null"]},
        "usage_evidence_url": {"type": ["string", "null"]},
        "quote": {"type": ["string", "null"]}},
        "required": ["is_investee", "is_paying_customer", "investment_evidence_url",
                     "usage_evidence_url", "quote"],
        "additionalProperties": False}
    resp = await youcom.research(
        f"Is {candidate['to']} both an investee of {candidate['from']} (or its fund/"
        f"credit program) AND a paying customer of {candidate['from']}'s products or API? "
        "Cite the investment announcement and independent usage evidence (case study, "
        "engineering blog, press) separately.",
        effort="standard", output_schema=schema)
    out = {"candidate": candidate, "result": resp["content"],
           "sources": resp["sources"][:5], "cost": resp["cost_usd"],
           "elapsed_ms": resp["elapsed_ms"], "cache_hit": False}
    await store.cache_put(key, "verify", out)
    return out


async def counterparty_verify(store, company: str, vendor: str,
                              ttl_hours: float = 24 * 7) -> dict:
    """S2-Q2 flagship: Research deep + sec.gov lock + typed schema."""
    key = f"S2-Q2-{company}"
    cached = await store.cache_get(key, "monthly", ttl_hours)
    if cached is not None:
        return {**cached, "cache_hit": True, "cost": 0.0}
    resp = await youcom.research(
        f"From {company}'s most recent 10-K, 10-Q or S-1 filing on sec.gov, extract: "
        f"(1) percent of supply sourced from {vendor} (supplier concentration), "
        f"(2) dollar value of purchase commitments to {vendor}, "
        "(3) customer concentration percentages, (4) debt secured by GPU collateral. "
        "Quote exact filing sentences. Populate findings with one entry per metric; "
        "value=null if not stated but include the most relevant quote.",
        effort="deep", source_control={"include_domains": ["sec.gov"]},
        output_schema=COUNTERPARTY_SCHEMA)
    out = {"content": resp["content"], "sources": resp["sources"][:6],
           "cost": resp["cost_usd"], "elapsed_ms": resp["elapsed_ms"], "cache_hit": False}
    await store.cache_put(key, "monthly", out)
    return out


async def arr_probe(store, lab: str, ttl_hours: float = 24.0) -> dict:
    """S1-Q5: newest reported ARR figure + the exact metric phrase (drift detector)."""
    key = f"S1-Q5-{lab}"
    cached = await store.cache_get(key, _today(), ttl_hours)
    if cached is not None:
        return {**cached, "cache_hit": True, "cost": 0.0}
    resp = await youcom.search(f"{lab} annualized revenue run-rate latest",
                               count=15, freshness="month")
    corpus = "\n\n".join(
        f"URL: {i.get('url')}\n{' '.join(i.get('snippets') or [])[:600]}"
        for i in (resp["results"].get("web") or [])[:10])
    try:
        ext = await haiku_json(
            f"Find the most recent {lab} revenue figure in the text. Output JSON: "
            '{"arr_usd_b": float|null, "metric_phrase": str|null, "as_of": str|null, '
            '"url": str|null}. Use ONLY figures stated in the text; annualized '
            "run-rate preferred; convert to billions USD.",
            corpus[:15000])
    except Exception:
        ext = {"arr_usd_b": None}
    out = {**ext, "cost": resp["cost_usd"], "cache_hit": False}
    await store.cache_put(key, _today(), out)
    return out


async def total_assets_usd_b(tickers: list[str]) -> float | None:
    """CR denominator: Σ totalAssets over the public universe (FMP, deterministic)."""
    import os
    key = os.environ.get("FMP_API_KEY", "")
    total = 0.0
    try:
        async with httpx.AsyncClient(timeout=30) as cli:
            for t in tickers:
                r = await cli.get(
                    f"https://financialmodelingprep.com/api/v3/balance-sheet-statement/{t}",
                    params={"limit": 1, "apikey": key})
                rows = r.json()
                if isinstance(rows, list) and rows:
                    total += rows[0].get("totalAssets", 0) or 0
        return round(total / 1e9, 1) if total else None
    except Exception:
        return None


# ------------------------------------------------------------------ CMI
def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def compute_cmi(curr: dict, base: dict | None, periods_in_base: int) -> float | None:
    """CMI vs cold-start baseline. base counts cover a wide window; divide to a
    per-period average so deltas compare like with like."""
    if not base:
        return None
    bf = (base.get("formation", 0) or 0) / max(1, periods_in_base)
    bd = (base.get("destruction", 0) or 0) / max(1, periods_in_base)
    df = _clamp(((curr.get("formation", 0) or 0) - bf) / 3.0)
    dd = _clamp(((curr.get("destruction", 0) or 0) - bd) / 3.0)
    di = _clamp((curr.get("intensity", 0) or 0) - (base.get("intensity", 0) or 0))
    return round(CMI_W["formation"] * df - CMI_W["destruction"] * dd
                 + CMI_W["intensity"] * di, 3)


async def cmi_history_append(store, stage: str, value: float | None) -> list[SeriesPoint]:
    hist = await store.cache_get(f"F3-CMI-{stage}", "history", ttl_hours=24 * 365) or {"points": []}
    pts = hist["points"]
    if value is not None:
        today = _today()
        pts = [p for p in pts if p["t"] != today] + [{"t": today, "v": value}]
        pts = pts[-12:]
        await store.cache_put(f"F3-CMI-{stage}", "history", {"points": pts})
    return [SeriesPoint(**p) for p in pts]


# ------------------------------------------------------------------ waterfall
def build_waterfall(lab: str, arr: dict, verified_f_edges_usd_b: float,
                    credit_low_b: float | None, credit_high_b: float | None) -> tuple[list[WaterfallBar], float | None]:
    if not arr.get("arr_usd_b"):
        return [], None
    a = float(arr["arr_usd_b"])
    bars = [WaterfallBar(label=f"Reported ARR ({arr.get('metric_phrase') or 'run-rate'})",
                         kind="reported", value_low=a, value_high=a,
                         citation_url=arr.get("url"))]
    ded_low = ded_high = verified_f_edges_usd_b
    bars.append(WaterfallBar(
        label="Portfolio-customer revenue (verified floor)", kind="deduction",
        value_low=verified_f_edges_usd_b, value_high=verified_f_edges_usd_b,
        note="verified F-edges only — a lower bound"))
    if credit_low_b is not None:
        bars.append(WaterfallBar(label="Credit-cohort usage inflation", kind="deduction",
                                 value_low=credit_low_b, value_high=credit_high_b,
                                 note="not GAAP revenue"))
        ded_low += credit_low_b
        ded_high += (credit_high_b or credit_low_b)
    else:
        bars.append(WaterfallBar(label="Credit-cohort usage inflation", kind="deduction",
                                 note="no sizing found this window — not deducted"))
    band_low, band_high = a - ded_high, a - ded_low
    bars.append(WaterfallBar(label="Cash-quality band", kind="result",
                             value_low=round(band_low, 1), value_high=round(band_high, 1)))
    rq = round(((band_low + band_high) / 2) / a, 2)
    return bars, rq
