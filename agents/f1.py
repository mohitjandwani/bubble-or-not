"""F1 Liquidity — rhetoric probe (SEARCH pattern) + score assembly.

Rhetoric: Search `include_domains=federalreserve.gov` + livecrawl markdown →
last 10 speeches by page_age → Haiku hawkishness rubric (temp 0, §5.3) →
delta = mean(last 5) − mean(prior 5).

F1 score (methodology §F1, renormalized over what our sources can honestly
provide): path steepness 0.30 + rhetoric 0.20 → /0.50. P(hike), time-to-
tightening (futures) and real rate (TIPS) have no allowed source → no-data.
"""
from __future__ import annotations

import asyncio
import re
from datetime import date, datetime, timezone

from schema import Evidence
from agents import youcom
from agents.llm import RHETORIC_SYSTEM, haiku_json
from agents.quant import norm

SPEECH_URL = re.compile(r"federalreserve\.gov/newsevents/speech/", re.I)


def _page_age_key(item: dict) -> str:
    return item.get("page_age") or "0000"


async def run_rhetoric_probe(store, run_id: str, ttl_hours: float = 24.0) -> dict:
    probe_id = "F1-rhetoric"
    window = str(date.today())
    cached = await store.cache_get(probe_id, window, ttl_hours)
    if cached is not None:
        return {**cached, "cache_hit": True, "cost": 0.0}

    resp = await youcom.search(
        "Federal Reserve speech monetary policy outlook",
        count=30, freshness="month", include_domains=["federalreserve.gov"],
        livecrawl="web")
    items = (resp["results"].get("web") or []) + (resp["results"].get("news") or [])
    speeches = [i for i in items if SPEECH_URL.search(i.get("url", ""))]
    speeches.sort(key=_page_age_key, reverse=True)
    speeches = speeches[:10]
    cost = resp["cost_usd"]

    # livecrawl markdown is best-effort — when it's missing/short, fetch the
    # full text through the Contents API (Search finds, Contents reads)
    thin = [s for s in speeches if len(s.get("markdown") or "") < 2500]
    if len(speeches) - len(thin) < 4 and thin:
        pages = await youcom.contents([s["url"] for s in thin])
        cost += pages["cost_usd"]
        by_url = {p.get("url"): p.get("markdown") or "" for p in pages["pages"]
                  if isinstance(p, dict)}
        for s in thin:
            if len(by_url.get(s["url"], "")) >= 2500:
                s["markdown"] = by_url[s["url"]]

    async def score(item: dict) -> dict | None:
        text = item.get("markdown") or " ".join(item.get("snippets") or [])
        # real speeches run thousands of chars; short pages are indexes/footnote
        # stubs that Haiku would (correctly) call boilerplate — skip them
        if not text or len(text) < 2500:
            return None
        try:
            r = await haiku_json(RHETORIC_SYSTEM, text[:12000])
            return {"url": item["url"], "title": item.get("title"),
                    "page_age": item.get("page_age"),
                    "score": float(r["score"]), "quote": r.get("evidence_quote", "")}
        except Exception:
            return None

    scored = [s for s in await asyncio.gather(*(score(i) for i in speeches)) if s]
    if len(scored) >= 4:
        half = len(scored) // 2
        recent, prior = scored[:half], scored[half:]
        delta = round(sum(s["score"] for s in recent) / len(recent)
                      - sum(s["score"] for s in prior) / len(prior), 2)
    else:
        delta = None  # too few speeches — honest no-data

    out = {"delta": delta, "speeches": scored, "n": len(scored),
           "cost": cost, "elapsed_ms": resp["elapsed_ms"], "cache_hit": False}
    await store.cache_put(probe_id, window, out)
    return out


def rhetoric_evidence(run_id: str, r: dict) -> list[Evidence]:
    rows = []
    for i, s in enumerate(r["speeches"][:5]):
        rows.append(Evidence(
            evidence_id=f"ev-{run_id}-F1-rhetoric-{i}", run_id=run_id, factor="f1",
            probe_id="F1-rhetoric", window=None, metric="hawkishness_score",
            value=s["score"], unit="[-1,+1]", as_of=None, quote=s["quote"],
            source_url=s["url"], confidence="medium",
            provenance={"endpoint": "search", "include_domains": "federalreserve.gov",
                        "livecrawl": "web", "scorer": "haiku rubric temp0",
                        "cost_usd": r["cost"], "cache_hit": r.get("cache_hit", False)}))
    return rows


def f1_score(steepness_bp: float | None, rhetoric_delta: float | None) -> tuple[float | None, dict]:
    parts, detail = [], {}
    if steepness_bp is not None:
        parts.append((0.30, norm(steepness_bp, 0, 200)))
        detail["path_steepness_bp"] = steepness_bp
    if rhetoric_delta is not None:
        parts.append((0.20, norm(rhetoric_delta, -1, 1)))
        detail["rhetoric_delta"] = rhetoric_delta
    if not parts:
        return None, detail
    w = sum(p[0] for p in parts)
    return round(100 * sum(wi * v for wi, v in parts) / w, 1), detail
