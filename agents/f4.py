"""F4 Insiders — mega-sale count (Pattern B) + narrative. Precise sell/buy
aggregates and %-of-ADV overhang have no clean allowed source → those
sub-metrics are no-data and the factor runs at medium confidence, flagged.

Score (§F4 renormalized): 0.30·norm(mega_sale_count, 0, 6) → /0.30 alone.
"""
from __future__ import annotations

from datetime import date

from schema import Evidence
from agents import youcom
from agents.extract import FINDING_TEMPLATE, extract
from agents.quant import norm

F4_EVENTS = ["mega_sale", "sale_program_10b5_1", "insider_buy", "none_found"]
F4_INPUT = (
    "For NVDA, MSFT, META, GOOGL, AVGO, AMZN, ORCL, CRWV in the last 90 days: "
    "individual insider sale programs or completed sales exceeding $100 million "
    "(founders, CEOs, directors). One finding per program/sale: EVENT mega_sale "
    "(or sale_program_10b5_1 if disclosed as a scheduled 10b5-1 plan; insider_buy "
    "for notable purchases). VALUE = dollar amount. DATE = announcement/filing date."
    + FINDING_TEMPLATE.format(enum=" | ".join(F4_EVENTS))
)


async def run_insider_probe(store, run_id: str, ttl_hours: float = 24.0) -> dict:
    probe_id = "F4-insider"
    window = str(date.today())
    cached = await store.cache_get(probe_id, window, ttl_hours)
    if cached is not None:
        resp, cache_hit = cached, True
    else:
        resp = await youcom.finance_research(F4_INPUT, effort="deep")
        await store.cache_put(probe_id, window, resp)
        cache_hit = False

    result = extract(resp["content"], resp["sources"], F4_EVENTS)
    mega = [f for f in result.findings if f.event == "mega_sale"]
    scheduled = [f for f in result.findings if f.event == "sale_program_10b5_1"]
    # 10b5-1 scheduled sales weight 0.5× (methodology edge case)
    effective_count = len(mega) + 0.5 * len(scheduled)

    evidence = []
    for i, f in enumerate(result.findings):
        evidence.append(Evidence(
            evidence_id=f"ev-{run_id}-F4-{i}", run_id=run_id, factor="f4",
            probe_id=probe_id, window=window, metric=f.event, value=None,
            unit="USD", as_of=f.date, quote=f.quote, source_url=f.source_url,
            confidence="medium",  # agentic aggregate, not a Form-4 feed — flagged
            provenance={"endpoint": "finance_research", "effort": "deep",
                        "cost_usd": 0.0 if cache_hit else resp["cost_usd"],
                        "cache_hit": cache_hit, "extract_stats": result.stats,
                        "value_text": f.value}))
    score = round(100 * norm(effective_count, 0, 6), 1)
    return {"mega_count": len(mega), "scheduled_count": len(scheduled),
            "effective_count": effective_count, "score": score,
            "evidence": evidence, "stats": result.stats,
            "cost": 0.0 if cache_hit else resp["cost_usd"], "cache_hit": cache_hit,
            "elapsed_ms": resp.get("elapsed_ms", 0)}
