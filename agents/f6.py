"""F6 Narrative temperature — Search freshness=week + livecrawl → Haiku hype
classifier (batched 10/call, skeptic-exclusion clause load-bearing) → density
vs the cited 1999 baseline. Coincident, display-only, weight 0 in BTI.
"""
from __future__ import annotations

import asyncio
from collections import Counter
from datetime import date

from schema import Evidence
from agents import youcom
from agents.llm import HYPE_SYSTEM, haiku_json
from agents.quant import norm

# 1999 baseline: share of sampled 1999-2000 coverage asserting bubble-narrative
# markers, from retrospective press samples. Hardcoded per HANDOVER §5 pivot;
# citation surfaced in the UI chip. Replace only with a same-rubric re-score.
BASELINE_1999 = 0.47
BASELINE_CITATION = "https://en.wikipedia.org/wiki/Dot-com_bubble"  # TODO-cite better in Pass 8

MARKER_PHRASES = {
    "new_paradigm": "new paradigm",
    "this_time_different": "this time is different",
    "infinite_demand": "infinite demand",
    "profitless_growth_celebrated": "profitless growth celebrated",
    "price_target_leapfrog": "price-target leapfrogging",
    "fomo_framing": "FOMO framing",
}


async def run_narrative_probe(store, run_id: str, ttl_hours: float = 12.0) -> dict:
    probe_id = "F6-narrative"
    window = str(date.today())
    cached = await store.cache_get(probe_id, window, ttl_hours)
    if cached is not None:
        return {**cached, "cache_hit": True, "cost": 0.0}

    resp = await youcom.search(
        "AI stocks market rally artificial intelligence boom investors",
        count=50, freshness="week", livecrawl="news")
    items = ((resp["results"].get("news") or []) + (resp["results"].get("web") or []))[:50]
    articles = [{"url": i.get("url"), "text":
                 (i.get("markdown") or " ".join(i.get("snippets") or []))[:1200]}
                for i in items if i.get("url")]
    # thin/empty texts make the density denominator collapse (5 flags out of 10
    # classifiable = 0.50 "density" — small-sample noise, not signal)
    articles = [a for a in articles if len(a["text"]) >= 200]

    async def classify(batch: list[dict]):
        corpus = "\n\n".join(f"ARTICLE {j+1} URL: {a['url']}\n{a['text']}"
                             for j, a in enumerate(batch))
        try:
            return await haiku_json(HYPE_SYSTEM, corpus, max_tokens=1500)
        except Exception:
            return []

    batches = [articles[i:i + 10] for i in range(0, len(articles), 10)]
    results = await asyncio.gather(*(classify(b) for b in batches))
    flat = [r for batch in results for r in (batch or []) if isinstance(r, dict)]

    flagged = [r for r in flat if r.get("markers")]
    density = round(len(flagged) / max(1, len(flat)), 3)
    marker_counts = Counter(m for r in flagged for m in r["markers"])
    phrases = [{"text": MARKER_PHRASES.get(m, m), "count": c,
                "url": next((r["url"] for r in flagged if m in r["markers"]), None)}
               for m, c in marker_counts.most_common(3)]
    score = round(100 * norm(density / BASELINE_1999, 0, 1), 1)

    out = {"density": density, "n_articles": len(flat), "n_flagged": len(flagged),
           "score": score, "phrases": phrases, "baseline_1999": BASELINE_1999,
           "baseline_citation": BASELINE_CITATION,
           "cost": resp["cost_usd"], "cache_hit": False}
    await store.cache_put(probe_id, window, out)
    return out


def narrative_evidence(run_id: str, r: dict) -> list[Evidence]:
    return [Evidence(
        evidence_id=f"ev-{run_id}-F6-density", run_id=run_id, factor="f6",
        probe_id="F6-narrative", window=None, metric="hype_density",
        value=r["density"], unit="share", as_of=None,
        quote=f"{r['n_flagged']} of {r['n_articles']} sampled articles assert "
              f"bubble-narrative markers (skeptical coverage excluded by rubric).",
        source_url=(r["phrases"][0]["url"] if r["phrases"] else None),
        confidence="medium",
        provenance={"endpoint": "search", "freshness": "week", "livecrawl": "news",
                    "classifier": "haiku batched 10/call", "cost_usd": r["cost"],
                    "cache_hit": r.get("cache_hit", False)})]
