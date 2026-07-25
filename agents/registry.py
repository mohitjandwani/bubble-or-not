"""Probe registry for Screen 2 ("Engine") — the judge-facing API-usage map.

Every entry carries the LITERAL input text / query / schema we send to You.com,
imported from the modules that actually send them — not paraphrases. If a
prompt changes in code, this page changes with it.
"""
from __future__ import annotations

import json

from agents.f2 import B1_STRONG_INPUT, B2_WEAK_INPUT, BINARY_SCHEMA, TONE_INPUT
from agents.f2_full import GROWTH_INPUT, TONE_UNIVERSE
from agents.f3 import (COUNTERPARTY_SCHEMA, DRIFT_SCHEMA, S1_B1_DRIFT, S2_B1_STRONG)
from agents.f3_run import (S1_DESTRUCTION_Q, S1_FORMATION_Q, S2_DISTRESS_Q,
                           S2_FORMATION_Q)
from agents.f4 import F4_INPUT
from agents.llm import HYPE_SYSTEM, RHETORIC_SYSTEM, TONE_SYSTEM


def _probe(probe_id, factor, pattern, endpoint, query, *, effort=None, params=None,
           schema=None, local_llm=None, cadence="run", cost_est=0.0, why=""):
    return {
        "probe_id": probe_id, "factor": factor, "pattern": pattern,
        "endpoint": endpoint, "effort": effort, "params": params or {},
        "query": query.strip() if query else None,
        "output_schema": json.dumps(schema, indent=1) if schema else None,
        "local_llm": local_llm, "cadence": cadence, "cost_est_usd": cost_est,
        "why_youcom": why,
    }


PROBE_REGISTRY: list[dict] = [
    # ---- F1 Liquidity ------------------------------------------------------
    _probe("F1-rhetoric", "f1", "SEARCH", "search + contents",
           "Federal Reserve speech monetary policy outlook",
           params={"include_domains": ["federalreserve.gov"], "freshness": "month",
                   "livecrawl": "web", "count": 30,
                   "fallback": "Contents API fetches full text when livecrawl markdown < 2500 chars"},
           local_llm=RHETORIC_SYSTEM, cost_est=0.03,
           why="Fed rhetoric is unstructured language — agentic search + a rubric "
               "beats any data feed. Domain lock = only primary sources."),
    _probe("F1-rates", "f1", "QUANT", "fmp", None, cost_est=0.0,
           why="Hard numbers (EFFR, 1Y treasury) come from a data feed, not an LLM — "
               "'agentic where research beats a feed, a feed where it beats research'."),
    # ---- F2 Bellwethers ----------------------------------------------------
    _probe("F2-B1", "f2", "A", "research", B1_STRONG_INPUT, effort="standard",
           params={"source_control.freshness": "explicit YYYY-MM-DDtoYYYY-MM-DD (90d)"},
           schema=BINARY_SCHEMA, cost_est=0.05,
           why="Binary strong-signal question. output_schema returns typed events — "
               "zero parsing; the LLM's strength label is advisory, config re-maps it."),
    _probe("F2-B2", "f2", "A", "research", B2_WEAK_INPUT, effort="standard",
           params={"source_control.freshness": "explicit range (30d)"},
           schema=BINARY_SCHEMA, cost_est=0.05,
           why="Weak-signal cluster detection (analyst cuts, renegotiation reports)."),
    _probe(f"F2-tone×{len(TONE_UNIVERSE)}", "f2", "B", "finance_research", TONE_INPUT,
           effort="deep", local_llm=TONE_SYSTEM, cost_est=0.11 * len(TONE_UNIVERSE),
           params={"universe": TONE_UNIVERSE, "chain": "FINDING template → shared extract() → tone rubric"},
           why="Transcripts live in the finance index (S&P-grade). Structure is "
               "recovered client-side via the FINDING template + regex→Haiku chain."),
    _probe("F2-growth", "f2", "B", "finance_research", GROWTH_INPUT, effort="deep",
           cost_est=0.11,
           why="NTM vs LTM growth needs estimate reconciliation — the finance index's strength."),
    _probe("F2-gpu-spot", "f2", "SEARCH", "search",
           "H100 GPU rental price per hour cloud marketplace spot",
           params={"freshness": "month", "livecrawl": "web", "count": 15,
                   "delta_rule": "30d change computed from OUR stored samples, never model memory"},
           cost_est=0.01, why="Physical demand telemetry — scrappy sources, flagged low confidence."),
    # ---- F3 Circularity (the showcase) --------------------------------------
    _probe("S1-B1", "f3", "A", "research", S1_B1_DRIFT, effort="standard",
           schema=DRIFT_SCHEMA, params={"freshness": "7d window"}, cadence="weekly",
           cost_est=0.05, why="Revenue-definition drift detector — mid-stage 1999 signature."),
    _probe("S1-Q1", "f3", "SEARCH", "search", S1_FORMATION_Q,
           params={"livecrawl": "news", "count": 30, "freshness": "7d"},
           cadence="weekly", cost_est=0.035,
           local_llm="Haiku entity extraction (§5.6): investor/recipient/amount/also_customer",
           why="Formation scan — feeds the EdgeVerifier fan-out."),
    _probe("S1-Q2 ×≤4", "f3", "A", "research",
           "Is <STARTUP> both an investee of <LAB>'s fund/credit program AND a paying "
           "customer of <LAB>'s products or API? Cite the investment announcement and "
           "independent usage evidence separately.",
           effort="standard", cadence="weekly (fan-out)", cost_est=0.20,
           why="THE fan-out: one scan expands into parallel verifications. Only edges "
               "verified on BOTH legs are scored — announced-only renders dimmed at $0."),
    _probe("S1-Q4", "f3", "SEARCH", "search", S1_DESTRUCTION_Q,
           params={"livecrawl": "news", "count": 30, "freshness": "7d"},
           cadence="weekly", cost_est=0.03,
           why="THE CANARY — usage-layer churn breaks first; deltas vs cold-start baseline."),
    _probe("S1-Q5 ×2", "f3", "SEARCH", "search",
           "<LAB> annualized revenue run-rate latest",
           params={"freshness": "month", "labs": ["OpenAI", "Anthropic"]},
           cadence="weekly", cost_est=0.01,
           why="ARR + exact metric phrase — the waterfall denominator and drift detector."),
    _probe("S2-B1", "f3", "A", "research", S2_B1_STRONG, effort="standard",
           schema=BINARY_SCHEMA, params={"freshness": "30d window"}, cadence="monthly",
           cost_est=0.05, why="GPU-layer strong events: cuts, impairments, canceled orders."),
    _probe("S2-Q1", "f3", "SEARCH", "search", S2_FORMATION_Q,
           params={"livecrawl": "news", "count": 30, "freshness": "30d"},
           cadence="monthly", cost_est=0.035, why="Capex-layer edge formation scan."),
    _probe("S2-Q2", "f3", "A", "research",
           "From <COUNTERPARTY>'s most recent 10-K/10-Q/S-1 on sec.gov: supplier "
           "concentration %, purchase commitments to <VENDOR> $, customer concentration, "
           "debt secured by GPU collateral. Quote exact filing sentences.",
           effort="deep", schema=COUNTERPARTY_SCHEMA,
           params={"source_control.include_domains": ["sec.gov"]},
           cadence="monthly", cost_est=0.10,
           why="THE FLAGSHIP: attribution lives on the counterparty side of filings. "
               "Domain lock + typed schema = quoted filing sentences as typed evidence."),
    _probe("S2-Q5", "f3", "SEARCH", "search", S2_DISTRESS_Q,
           params={"livecrawl": "news", "count": 30, "freshness": "30d"},
           cadence="monthly", cost_est=0.03,
           why="THE AVALANCHE — any hit on a registry edge is a late-stage signature."),
    # ---- F4 Insiders ---------------------------------------------------------
    _probe("F4-insider", "f4", "B", "finance_research", F4_INPUT, effort="deep",
           cost_est=0.11,
           why="Mega-sales are news-covered; precise Form-4 aggregates have no allowed "
               "source → that sub-metric is honestly no-data."),
    # ---- F5 Breadth ----------------------------------------------------------
    _probe("F5-quant ×4", "f5", "QUANT", "fmp + yfinance", None, cost_est=0.0,
           why="Pure math over 501 constituents — the 'no LLM in this row' factor. "
               "You.com adds nothing as source-of-truth here, and that's the point."),
    # ---- F6 Narrative ---------------------------------------------------------
    _probe("F6-narrative", "f6", "SEARCH", "search",
           "AI stocks market rally artificial intelligence boom investors",
           params={"freshness": "week", "count": 50, "livecrawl": "news"},
           local_llm=HYPE_SYSTEM, cost_est=0.06,
           why="Real-time media sampling is exactly what the Search API is for. The "
               "skeptic-exclusion clause keeps coverage ABOUT bubble fear from counting as hype."),
]
