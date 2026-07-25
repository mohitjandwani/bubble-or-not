"""F2 Bellwethers — the first REAL You.com agent (Pass 3 vertical slice).

Three live probes:
  F2-B1  Pattern A · Research `standard` + binary-events output_schema + freshness window
         — the strong questions (guidance cuts, NVIDIA demand language, reported misses)
  F2-B2  Pattern A · same shape — the weak questions (analyst cuts, contract renegotiations)
  F2-tone-NVDA  Pattern B · Finance Research `deep` + FINDING template → shared extract()

Design law enforced here: the model's `signal_strength` label is ADVISORY —
config/events.yaml re-maps event_type → strength deterministically, and the
lamp comes from counters + thresholds, never from the LLM.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

from schema import Evidence
from agents import youcom
from agents.extract import FINDING_TEMPLATE, extract

ROOT = Path(__file__).resolve().parents[1]
EVENT_STRENGTH: dict[str, str] = yaml.safe_load(
    (ROOT / "config/events.yaml").read_text())["event_strength"]

BINARY_SCHEMA = {  # HANDOVER §4, verbatim shape
    "type": "object",
    "properties": {
        "answer": {"type": "boolean"},
        "events": {"type": "array", "items": {"type": "object", "properties": {
            "company": {"type": "string"},
            "event_type": {"type": "string", "enum": [
                "guidance_cut", "guidance_withdrawn", "reported_miss",
                "analyst_estimate_cut", "impairment", "order_cancellation",
                "covenant_issue"]},
            "signal_strength": {"type": "string", "enum": ["strong", "weak"]},
            "date": {"type": ["string", "null"]},
            "magnitude": {"type": ["string", "null"]},
            "quote": {"type": "string"},
            "source_url": {"type": "string"}},
            "required": ["company", "event_type", "signal_strength", "date",
                         "magnitude", "quote", "source_url"],
            "additionalProperties": False}}},
    "required": ["answer", "events"], "additionalProperties": False}

B1_STRONG_INPUT = (
    "Answer for the period covered by the search window. Has any of the following occurred?\n"
    "1. A publicly traded neocloud or AI-infrastructure company (CoreWeave, Nebius, "
    "Lambda, Applied Digital, or similar) lowered or withdrew its own revenue, cash-flow, "
    "or capex guidance.\n"
    "2. NVIDIA lowered its guidance or management softened forward demand language in "
    "official communications (earnings calls, filings, investor events).\n"
    "3. Any neocloud reported revenue or operating cash flow below its own prior guidance, "
    "took an impairment, disclosed a covenant issue, or had a GPU order canceled.\n"
    "Set answer=true if any occurred. One event object per occurrence, only if explicitly "
    "supported by a source; quote = the exact sentence; use null for unknown fields. "
    "If none occurred, answer=false with an empty events array."
)

B2_WEAK_INPUT = (
    "Answer for the period covered by the search window. Has any of the following occurred?\n"
    "1. Sell-side analysts cut revenue/EPS estimates or price targets for NVIDIA, "
    "CoreWeave, Nebius, or other AI-infrastructure names.\n"
    "2. Reports that AI compute contracts are being renegotiated, downsized, or delayed.\n"
    "Set answer=true if any occurred. One event object per occurrence (use event_type "
    "analyst_estimate_cut for estimate/price-target cuts; order_cancellation for "
    "contract renegotiation reports), only if explicitly supported by a source; "
    "quote = the exact sentence; null for unknown fields."
)

TONE_EVENTS = ["guidance_raised", "guidance_maintained", "guidance_lowered",
               "guidance_withdrawn", "none_found"]
TONE_INPUT = (
    "For NVIDIA's most recent earnings call and quarterly filing: management's forward "
    "guidance, whether guidance was raised/maintained/lowered/withdrawn, the specific "
    "forward-looking language used about demand, and any hedging or qualifying language."
    + FINDING_TEMPLATE.format(enum=" | ".join(TONE_EVENTS))
)


def _window(days: int) -> str:
    end = date.today()
    return f"{end - timedelta(days=days)}to{end}"


def _in_window(event_date: str | None, window: str) -> bool:
    """Recency layer 3: extracted event date must fall inside the window.
    Undated events pass (can't disprove) but carry medium confidence."""
    if not event_date:
        return True
    try:
        d = date.fromisoformat(event_date[:10])
    except ValueError:
        return True
    start_s, end_s = window.split("to")
    return date.fromisoformat(start_s) <= d <= date.fromisoformat(end_s)


async def run_binary_probe(store, run_id: str, probe_id: str, input_text: str,
                           window_days: int, ttl_hours: float = 12.0) -> dict:
    """One Pattern A binary probe → typed events → evidence rows + counters.
    Returns {events, evidence, strong, weak, cost, cache_hit, excluded}."""
    window = _window(window_days)
    cached = await store.cache_get(probe_id, window, ttl_hours)
    if cached is not None:
        resp, cache_hit = cached, True
    else:
        resp = await youcom.research(input_text, effort="standard",
                                     source_control={"freshness": window},
                                     output_schema=BINARY_SCHEMA)
        await store.cache_put(probe_id, window, resp)
        resp, cache_hit = resp, False

    content = resp["content"] or {}
    events = content.get("events", []) if isinstance(content, dict) else []
    strong = weak = 0
    evidence: list[Evidence] = []
    excluded: list[dict] = []
    for i, ev in enumerate(events):
        # deterministic re-map — the LLM's signal_strength is advisory only
        strength = EVENT_STRENGTH.get(ev.get("event_type", ""), "weak")
        if not _in_window(ev.get("date"), window):
            excluded.append({**ev, "excluded_reason": "event date outside window"})
            continue
        if strength == "strong":
            strong += 1
        else:
            weak += 1
        evidence.append(Evidence(
            evidence_id=f"ev-{run_id}-{probe_id}-{i}", run_id=run_id, factor="f2",
            probe_id=probe_id, window=window, metric=ev.get("event_type", "event"),
            value=None, unit=None,
            as_of=ev.get("date")[:10] if ev.get("date") else None,
            quote=ev.get("quote"), source_url=ev.get("source_url"),
            confidence="high" if (strength == "strong" and ev.get("date")) else "medium",
            provenance={"endpoint": "research", "effort": "standard",
                        "freshness": window, "cost_usd": resp["cost_usd"],
                        "elapsed_ms": resp["elapsed_ms"], "cache_hit": cache_hit,
                        "llm_strength_advisory": ev.get("signal_strength"),
                        "strength_used": strength}))
    return {"events": events, "evidence": evidence, "strong": strong, "weak": weak,
            "cost": 0.0 if cache_hit else resp["cost_usd"], "cache_hit": cache_hit,
            "excluded": excluded, "window": window,
            "answer": bool(content.get("answer")) if isinstance(content, dict) else False,
            "elapsed_ms": resp["elapsed_ms"]}


async def run_tone_probe(store, run_id: str, ticker: str = "NVDA",
                         ttl_hours: float = 24.0) -> dict:
    """Pattern B: Finance Research → shared extract(). Proves the chain live."""
    probe_id = f"F2-tone-{ticker}"
    window = str(date.today())  # tone is point-in-time, keyed by day
    cached = await store.cache_get(probe_id, window, ttl_hours)
    if cached is not None:
        resp, cache_hit = cached, True
    else:
        resp = await youcom.finance_research(TONE_INPUT, effort="deep")
        await store.cache_put(probe_id, window, resp)
        cache_hit = False

    result = extract(resp["content"], resp["sources"], TONE_EVENTS)
    evidence = []
    for i, f in enumerate(result.findings):
        evidence.append(Evidence(
            evidence_id=f"ev-{run_id}-{probe_id}-{i}", run_id=run_id, factor="f2",
            probe_id=probe_id, window=window, metric=f.event, value=None, unit=None,
            as_of=f.date, quote=f.quote, source_url=f.source_url, confidence="medium",
            provenance={"endpoint": "finance_research", "effort": "deep",
                        "cost_usd": resp["cost_usd"], "elapsed_ms": resp["elapsed_ms"],
                        "cache_hit": cache_hit, "extract_stats": result.stats}))
    # failed blocks become low-confidence, score-excluded rows — visible, never silent
    for j, bad in enumerate(result.failed_blocks):
        evidence.append(Evidence(
            evidence_id=f"ev-{run_id}-{probe_id}-fail{j}", run_id=run_id, factor="f2",
            probe_id=probe_id, window=window, metric="extract_failed", value=None,
            unit=None, as_of=None, quote=bad[:300], source_url=None, confidence="low",
            provenance={"endpoint": "finance_research", "excluded_from_score": True,
                        "extract_stats": result.stats}))
    return {"evidence": evidence, "stats": result.stats,
            "raw_md_head": resp["content"][:500],
            "cost": 0.0 if cache_hit else resp["cost_usd"], "cache_hit": cache_hit,
            "elapsed_ms": resp["elapsed_ms"]}
