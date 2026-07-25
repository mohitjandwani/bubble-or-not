"""F3 orchestration: Stage1Agent + Stage2Agent + reduce. Called by the pipeline.

The trace money-shot: S1-Q1 scan emits one tool_call, then N parallel S1-Q2
verify tool_calls — one scan expanding into a fan-out, visible in run_events.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from schema import Evidence, StatePayload
from agents import youcom
from agents.f2 import run_binary_probe
from agents.f3 import (COUNTERPARTY_SCHEMA, DRIFT_SCHEMA, S1_B1_DRIFT, S2_B1_STRONG,
                       VERIFY_FANOUT_CAP, arr_probe, build_waterfall, cmi_history_append,
                       compute_cmi, counterparty_verify, dedup_vs_registry,
                       extract_candidate_edges, load_registry, scan_probe,
                       total_assets_usd_b, verify_edge)
from agents.llm import haiku_json
from agents.quant import norm

LABS = ["OpenAI", "Anthropic"]
UNIVERSE_ASSETS_TICKERS = ["NVDA", "MSFT", "META", "GOOGL", "AVGO", "AMZN", "ORCL", "CRWV"]

S1_FORMATION_Q = ("OpenAI Startup Fund OR Anthropic investment new startup announcement "
                  "API customer")
S1_DESTRUCTION_Q = ("AI startup shutdown OR winding down OR acquihire OR pivots away "
                    "API costs burn rate")
S2_FORMATION_Q = ("NVIDIA OR AMD investment neocloud equity stake purchase agreement GPUs "
                  "chipmaker backstop capacity")
S2_DISTRESS_Q = ("neocloud OR AI data center canceled OR delayed OR renegotiated GPU "
                 "order impairment writedown covenant")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_date(v) -> str | None:
    """LLM date fields are free text; Evidence.as_of is a date. Strict or None."""
    import re
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", str(v or ""))
    return m.group(1) if m else None


async def _count_events(items: list[dict], instruction: str) -> tuple[int, list[dict]]:
    """Haiku counts distinct qualifying events in scan results. Returns
    (count, [{name, url, quote}]). Zero on classifier failure — never guesses."""
    if not items:
        return 0, []
    corpus = "\n\n".join(f"URL: {i['url']}\nTITLE: {i['title']}\n{i['text'][:800]}"
                         for i in items[:20])
    try:
        out = await haiku_json(
            instruction + ' Output JSON: {"events": [{"name": str, "url": str, '
            '"quote": str}]}. Only events explicitly stated in the text; one entry '
            "per distinct company/deal (dedupe repeat coverage).",
            corpus[:22000], max_tokens=1200)
        events = out.get("events", []) if isinstance(out, dict) else []
        return len(events), events[:8]
    except Exception:
        return 0, []


async def run_f3(store, state: StatePayload, run_id: str, emit, baseline_mode: bool = False) -> float:
    """Execute both stages. baseline_mode widens windows and stores window-0
    counts instead of computing deltas (the cold-start battery)."""
    cost = 0.0
    registry = load_registry()
    evidence: list[Evidence] = []
    s1_days, s2_days = (30, 365) if baseline_mode else (7, 30)

    async def tool(probe_id: str, endpoint: str, r: dict, **detail) -> None:
        nonlocal cost
        cost += r.get("cost", 0.0)
        await emit("agent.tool_call", factor="f3", probe_id=probe_id, endpoint=endpoint,
                   cost=r.get("cost", 0.0), elapsed_ms=r.get("elapsed_ms", 0),
                   cache_hit=r.get("cache_hit", False), detail=detail)

    # ============================= STAGE 1 (usage layer) ======================
    async def stage1() -> dict:
        b1 = await run_binary_probe(store, run_id, "S1-B1", S1_B1_DRIFT, s1_days,
                                    factor="f3", schema=DRIFT_SCHEMA)
        await tool("S1-B1", "research", b1, answer=b1["answer"], events=len(b1["events"]))
        evidence.extend(b1["evidence"])

        scan = await scan_probe(store, "S1-Q1", S1_FORMATION_Q, s1_days)
        await tool("S1-Q1", "search", scan, items=len(scan["items"]))
        candidates = dedup_vs_registry(await extract_candidate_edges(scan["items"]), registry)
        # EdgeVerifier also (re)verifies announced-only registry F-edges — the
        # registry is seeded from press; verification is what upgrades an edge
        # to scored. New scan candidates take priority in the fan-out cap.
        registry_todo = [{"from": e.from_entity, "to": e.to_entity,
                          "amount_usd_m": e.amount_usd_m, "url": e.seed_source_url,
                          "_edge_id": e.edge_id}
                         for e in registry
                         if e.archetype == "F" and e.status == "announced_only"]
        fan_out = (candidates + registry_todo)[:VERIFY_FANOUT_CAP]
        await emit("agent.evidence", factor="f3",
                   detail={"stage": 1, "new_candidates": len(candidates),
                           "registry_unverified": len(registry_todo),
                           "fan_out": len(fan_out)})

        # THE FAN-OUT: one scan → N parallel verifications
        verifications = await asyncio.gather(
            *(verify_edge(store, c) for c in fan_out),
            return_exceptions=True)
        verified_f = []
        for v in verifications:
            if isinstance(v, Exception):
                continue
            c, res = v["candidate"], v["result"] or {}
            await tool(f"S1-Q2:{c['to'][:14]}", "research", v,
                       investee=res.get("is_investee"), customer=res.get("is_paying_customer"))
            if res.get("is_investee") and res.get("is_paying_customer"):
                verified_f.append({**c, "usage_url": res.get("usage_evidence_url"),
                                   "quote": res.get("quote")})
                if c.get("_edge_id"):  # upgrade the registry edge
                    for e in registry:
                        if e.edge_id == c["_edge_id"]:
                            e.status = "verified"
                evidence.append(Evidence(
                    evidence_id=f"ev-{run_id}-S1Q2-{c['to'][:10]}", run_id=run_id,
                    factor="f3", probe_id="S1-Q2", window=str(s1_days) + "d",
                    metric="verified_f_edge", value=c.get("amount_usd_m"), unit="$M",
                    as_of=None, quote=res.get("quote"),
                    source_url=res.get("usage_evidence_url") or c.get("url"),
                    confidence="medium",
                    provenance={"endpoint": "research", "effort": "standard",
                                "pattern": "A", "from": c["from"], "to": c["to"]}))

        dest = await scan_probe(store, "S1-Q4", S1_DESTRUCTION_Q, s1_days)
        await tool("S1-Q4", "search", dest, items=len(dest["items"]))
        d_count, d_events = await _count_events(
            dest["items"], "Count DISTINCT AI startups reported as shutting down, winding "
            "down, being acquihired, or pivoting away from AI due to API/compute costs.")
        for j, e in enumerate(d_events[:4]):
            evidence.append(Evidence(
                evidence_id=f"ev-{run_id}-S1Q4-{j}", run_id=run_id, factor="f3",
                probe_id="S1-Q4", window=f"{s1_days}d", metric="usage_destruction",
                value=None, unit=None, as_of=None, quote=e.get("quote"),
                source_url=e.get("url"), confidence="medium",
                provenance={"endpoint": "search", "livecrawl": "news", "canary": True}))

        arrs = {}
        for lab in LABS:
            a = await arr_probe(store, lab)
            await tool(f"S1-Q5:{lab}", "search", a, arr_usd_b=a.get("arr_usd_b"))
            arrs[lab] = a
            if a.get("arr_usd_b"):
                evidence.append(Evidence(
                    evidence_id=f"ev-{run_id}-S1Q5-{lab}", run_id=run_id, factor="f3",
                    probe_id="S1-Q5", window="month", metric="reported_arr",
                    value=a["arr_usd_b"], unit="$B", as_of=_clean_date(a.get("as_of")),
                    quote=f"{lab}: {a.get('metric_phrase') or 'annualized run-rate'} "
                          f"${a['arr_usd_b']}B", source_url=a.get("url"),
                    confidence="medium", provenance={"endpoint": "search",
                                                     "drift_detector": a.get("metric_phrase")}))
        return {"b1": b1, "formation": len(candidates), "destruction": d_count,
                "intensity": 0.0, "verified_f": verified_f, "arrs": arrs,
                "d_events": d_events}

    # ============================= STAGE 2 (GPU layer) ========================
    async def stage2() -> dict:
        b1 = await run_binary_probe(store, run_id, "S2-B1", S2_B1_STRONG, s2_days,
                                    factor="f3")
        await tool("S2-B1", "research", b1, answer=b1["answer"], events=len(b1["events"]))
        evidence.extend(b1["evidence"])

        scan = await scan_probe(store, "S2-Q1", S2_FORMATION_Q, s2_days)
        await tool("S2-Q1", "search", scan, items=len(scan["items"]))
        candidates = dedup_vs_registry(await extract_candidate_edges(scan["items"]), registry)

        cp = await counterparty_verify(store, "CoreWeave", "NVIDIA")
        await tool("S2-Q2:CoreWeave", "research", cp,
                   findings=len((cp["content"] or {}).get("findings", [])))
        cp_findings = (cp["content"] or {}).get("findings", [])
        commitments_usd = None
        for j, f in enumerate(cp_findings):
            if f.get("metric") == "purchase_commitments_usd" and f.get("value"):
                commitments_usd = f["value"]
            if f.get("quote"):
                evidence.append(Evidence(
                    evidence_id=f"ev-{run_id}-S2Q2-{j}", run_id=run_id, factor="f3",
                    probe_id="S2-Q2", window="monthly", metric=f["metric"],
                    value=f.get("value"), unit=f.get("unit"), as_of=None,
                    quote=f["quote"], source_url=f.get("source_url"),
                    confidence="high" if f.get("value") else "medium",
                    provenance={"endpoint": "research", "effort": "deep",
                                "include_domains": "sec.gov", "pattern": "A",
                                "cost_usd": cp["cost"]}))
        # counterparty corroboration upgrades NVIDIA->CoreWeave edges to verified
        if cp_findings:
            for e in registry:
                if "nvidia" in e.from_entity.lower() and "coreweave" in e.to_entity.lower():
                    e.status = "verified"

        dist = await scan_probe(store, "S2-Q5", S2_DISTRESS_Q, s2_days)
        await tool("S2-Q5", "search", dist, items=len(dist["items"]))
        names = {e.from_entity.lower() for e in registry} | {e.to_entity.lower() for e in registry}
        d_count, d_events = await _count_events(
            dist["items"], "Count DISTINCT canceled, delayed, or renegotiated GPU orders, "
            "datacenter buildouts, impairments, writedowns, or covenant issues at AI "
            "infrastructure companies.")
        registry_hits = [e for e in d_events
                         if any(n in (e.get("name") or "").lower() for n in names)]
        for j, e in enumerate(d_events[:4]):
            evidence.append(Evidence(
                evidence_id=f"ev-{run_id}-S2Q5-{j}", run_id=run_id, factor="f3",
                probe_id="S2-Q5", window=f"{s2_days}d", metric="capex_distress",
                value=None, unit=None, as_of=None, quote=e.get("quote"),
                source_url=e.get("url"), confidence="medium",
                provenance={"endpoint": "search", "livecrawl": "news", "avalanche": True,
                            "registry_hit": e in registry_hits}))
        return {"b1": b1, "formation": len(candidates), "destruction": d_count,
                "intensity": 0.0, "registry_hits": registry_hits,
                "commitments_usd": commitments_usd}

    s1, s2 = await asyncio.gather(stage1(), stage2())

    # ============================= REDUCE =====================================
    if baseline_mode:
        await store.cache_put("F3-baseline-s1", "window0",
                              {k: s1[k] for k in ("formation", "destruction", "intensity")})
        await store.cache_put("F3-baseline-s2", "window0",
                              {k: s2[k] for k in ("formation", "destruction", "intensity")})
        # no evidence write: baseline runs have no `runs` row (FK) — counts only
        return cost

    base_s1 = await store.cache_get("F3-baseline-s1", "window0", ttl_hours=24 * 365)
    base_s2 = await store.cache_get("F3-baseline-s2", "window0", ttl_hours=24 * 365)
    cmi_s1 = compute_cmi(s1, base_s1, periods_in_base=4)     # month baseline → 4 wks
    cmi_s2 = compute_cmi(s2, base_s2, periods_in_base=12)    # year baseline → 12 mo

    # Circularity Ratio: verified circular $ / universe total assets
    verified_usd_m = sum(e.amount_usd_m or 0 for e in registry if e.status == "verified")
    assets_b = await total_assets_usd_b(UNIVERSE_ASSETS_TICKERS)
    cr_pct = round((verified_usd_m / 1000) / assets_b * 100, 2) if assets_b else None
    if cr_pct is not None:
        evidence.append(Evidence(
            evidence_id=f"ev-{run_id}-CR", run_id=run_id, factor="f3", probe_id="F3-CR",
            window=None, metric="circularity_ratio_pct", value=cr_pct, unit="%",
            as_of=None,
            quote=f"${verified_usd_m/1000:.1f}B verified circular edges / "
                  f"${assets_b:.0f}B universe total assets (FMP balance sheets).",
            source_url="https://financialmodelingprep.com", confidence="medium",
            provenance={"computed": "deterministic", "verified_edges":
                        [e.edge_id for e in registry if e.status == "verified"]}))

    # Waterfalls (verified F-edge $ per lab)
    waterfalls, rq = {}, {}
    for lab in LABS:
        f_usd_b = sum((v.get("amount_usd_m") or 0) / 1000 for v in s1["verified_f"]
                      if lab.lower() in (v.get("from") or "").lower())
        bars, rq_score = build_waterfall(lab, s1["arrs"].get(lab, {}), round(f_usd_b, 2),
                                         None, None)
        if bars:
            waterfalls[lab] = bars
            rq[lab] = rq_score

    # F3 sub-score (battery §3): CR 50% · CMI_s2 25% · CMI_s1 25%, renormalized
    parts = []
    if cr_pct is not None:
        parts.append((0.50, norm(cr_pct, 0, 8)))
    if cmi_s2 is not None:
        parts.append((0.25, (cmi_s2 + 1) / 2))
    if cmi_s1 is not None:
        parts.append((0.25, (cmi_s1 + 1) / 2))
    score = round(100 * sum(w * v for w, v in parts) / sum(w for w, _ in parts), 1) if parts else None

    # ---- signatures ----------------------------------------------------------
    def sig(sig_id):
        return next(x for x in state.signatures if x.signature_id == sig_id)

    s = sig("sig-f3-drift")
    drift_events = [e for e in s1["b1"]["events"]
                    if e.get("event_type") == "revenue_definition_change"]
    s.strong_count, s.weak_count = len(drift_events), len(s1["b1"]["events"]) - len(drift_events)
    s.lamp = "fired" if s.strong_count else ("watch" if s.weak_count else "not")
    s.current_reading = (drift_events[0]["quote"][:90] if drift_events else
                         "No revenue-metric redefinitions found this window")
    s.confidence = "high" if drift_events else "medium"
    s.driving_evidence_ids = [e.evidence_id for e in s1["b1"]["evidence"]]

    s = sig("sig-f3-churn")
    base_wk = ((base_s1 or {}).get("destruction", 0) or 0) / 4
    accel = s1["destruction"] > 1.5 * base_wk if base_s1 else None
    hist = await store.cache_get("F3-churn-accel", "history", 24 * 365) or {"consec": 0}
    consec = (hist["consec"] + 1) if accel else 0
    await store.cache_put("F3-churn-accel", "history", {"consec": consec})
    s.strong_count = 1 if consec >= 2 else 0
    s.weak_count = s1["destruction"]
    if accel is None:
        s.lamp, s.no_data_reason = "no_data", "no cold-start baseline yet — run scripts/cold_start_f3.py"
    else:
        s.no_data_reason = None
        s.lamp = "fired" if consec >= 2 else ("partial" if consec == 1 else
                                              ("watch" if s1["destruction"] else "not"))
    s.current_reading = (f"{s1['destruction']} shutdown/pivot events this week vs "
                         f"{base_wk:.1f}/wk baseline" if base_s1 else
                         f"{s1['destruction']} shutdown/pivot events (no baseline)")
    s.confidence = "medium"
    s.driving_evidence_ids = [f"ev-{run_id}-S1Q4-{j}" for j in range(min(4, len(s1["d_events"])))]

    s = sig("sig-f3-vendor")
    rq_min = min((v for v in rq.values() if v is not None), default=None)
    fired = (cr_pct is not None and cr_pct >= 1.0) or (rq_min is not None and rq_min <= 0.6)
    s.strong_count, s.weak_count = (1 if fired else 0), 0
    s.lamp = "fired" if fired else "not"
    s.current_reading = (f"Circularity Ratio {cr_pct}% of universe assets"
                         + (f" · min RQ {rq_min}" if rq_min is not None else "")
                         if cr_pct is not None else "CR not computable (assets fetch failed)")
    s.confidence = "medium"
    s.driving_evidence_ids = [f"ev-{run_id}-CR"]

    s = sig("sig-f3-distress")
    strong_s2 = s2["b1"]["strong"] + len(s2["registry_hits"])
    s.strong_count, s.weak_count = strong_s2, s2["b1"]["weak"]
    s.lamp = "fired" if strong_s2 else ("watch" if s2["destruction"] else "not")
    s.current_reading = (f"{strong_s2} strong distress events on registry edges" if strong_s2
                         else f"{s2['destruction']} distress mentions — none on registry edges")
    s.confidence = "high" if strong_s2 else "medium"
    s.driving_evidence_ids = [e.evidence_id for e in s2["b1"]["evidence"]]

    # ---- exhibit + factor ----------------------------------------------------
    state.f3.cmi_stage1 = await cmi_history_append(store, "s1", cmi_s1)
    state.f3.cmi_stage2 = await cmi_history_append(store, "s2", cmi_s2)
    state.f3.prebreak = bool(cmi_s1 is not None and cmi_s2 is not None
                             and cmi_s1 < 0 < cmi_s2)
    state.f3.circularity_ratio_pct = cr_pct
    state.f3.waterfalls = waterfalls
    state.f3.revenue_quality = rq
    state.f3.edges = registry

    f3 = next(x for x in state.factors if x.factor == "f3")
    if score is not None:
        f3.score = score
    f3.state = "ok" if (cr_pct is not None and cmi_s1 is not None) else "low_coverage"
    f3.sub_metrics = {"circularity_ratio_pct": cr_pct, "cmi_stage1": cmi_s1,
                      "cmi_stage2": cmi_s2, "verified_edges":
                      sum(1 for e in registry if e.status == "verified"),
                      "announced_only_edges":
                      sum(1 for e in registry if e.status == "announced_only"),
                      "s1_formation": s1["formation"], "s1_destruction": s1["destruction"],
                      "s2_formation": s2["formation"], "s2_destruction": s2["destruction"],
                      "revenue_quality": rq}
    f3.cost, f3.as_of = round(cost, 4), _now()

    await store.put_evidence(run_id, evidence)
    await emit("agent.evidence", factor="f3", detail={"count": len(evidence)})
    return cost
