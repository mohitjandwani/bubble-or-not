"""You.com API client — research / finance_research / search / balance.

Every call returns a normalized dict:
  {content, content_type, sources[], cost_usd, elapsed_ms}
Costs are accounted per call from the published pricing (HANDOVER §2); the
pipeline emits them into run_events so total spend is auditable per run.
One retry on transport errors / 5xx. Research calls can take minutes — long timeout.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, Optional

import httpx

API = "https://api.you.com/v1"
INDEX = "https://ydc-index.io/v1"

COST = {  # $ per call (search/contents per §2 pricing, /1k → per call)
    ("research", "lite"): 0.012,
    ("research", "standard"): 0.05,
    ("research", "deep"): 0.10,
    ("research", "exhaustive"): 0.45,
    ("finance_research", "deep"): 0.11,
    ("finance_research", "exhaustive"): 0.45,
    ("search", None): 0.005,
    ("contents", None): 0.001,
}


class YouError(RuntimeError):
    pass


# Per-endpoint concurrency caps (agents-README §4: search 5, research 3)
SEM = {"search": asyncio.Semaphore(5), "research": asyncio.Semaphore(3),
       "finance_research": asyncio.Semaphore(4), "contents": asyncio.Semaphore(5)}


def _key() -> str:
    return os.environ["YOU_API_KEY"]


async def _post(url: str, payload: dict, timeout: float = 420) -> dict:
    last: Exception | None = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=timeout) as cli:
                r = await cli.post(url, headers={"X-API-Key": _key()}, json=payload)
            if r.status_code >= 500:
                raise YouError(f"{url} -> {r.status_code}: {r.text[:200]}")
            if r.status_code != 200:
                # 4xx is our bug (schema/params) — no retry, fail loud
                raise YouError(f"{url} -> {r.status_code}: {r.text[:400]}")
            return r.json()
        except (httpx.HTTPError, YouError) as exc:
            last = exc
            if attempt == 0 and not (isinstance(exc, YouError) and "-> 4" in str(exc)):
                await asyncio.sleep(2)
                continue
            raise
    raise last  # unreachable


async def research(input_text: str, effort: str = "standard",
                   source_control: Optional[dict] = None,
                   output_schema: Optional[dict] = None) -> dict:
    payload: dict[str, Any] = {"input": input_text, "research_effort": effort}
    if source_control:
        payload["source_control"] = source_control
    if output_schema:
        payload["output_schema"] = output_schema
    t0 = time.monotonic()
    async with SEM["research"]:
        body = await _post(f"{API}/research", payload)
    out = body.get("output", body)
    content = out.get("content")
    if output_schema and isinstance(content, str):
        content = json.loads(content)
    return {"content": content, "content_type": out.get("content_type"),
            "sources": out.get("sources") or [],
            "cost_usd": COST[("research", effort)],
            "elapsed_ms": int((time.monotonic() - t0) * 1000)}


async def finance_research(input_text: str, effort: str = "deep") -> dict:
    t0 = time.monotonic()
    async with SEM["finance_research"]:
        body = await _post(f"{API}/finance_research",
                           {"input": input_text, "research_effort": effort})
    out = body.get("output", body)
    return {"content": out.get("content") or "", "content_type": out.get("content_type"),
            "sources": out.get("sources") or [],
            "cost_usd": COST[("finance_research", effort)],
            "elapsed_ms": int((time.monotonic() - t0) * 1000)}


async def search(query: str, *, count: int = 20, freshness: Optional[str] = None,
                 include_domains: Optional[list[str]] = None,
                 livecrawl: Optional[str] = None) -> dict:
    params: dict[str, Any] = {"query": query, "count": count}
    if freshness:
        params["freshness"] = freshness
    if include_domains:
        params["include_domains"] = include_domains
    if livecrawl:
        params["livecrawl"] = livecrawl
        params["livecrawl_formats"] = ["markdown"]
    t0 = time.monotonic()
    async with SEM["search"], httpx.AsyncClient(timeout=60) as cli:
        r = await cli.get(f"{INDEX}/search", headers={"X-API-Key": _key()}, params=params)
    if r.status_code != 200:
        raise YouError(f"search -> {r.status_code}: {r.text[:300]}")
    body = r.json()
    results = body.get("results", {})
    n_pages = len(results.get("web", [])) + len(results.get("news", []))
    cost = COST[("search", None)] + (0.001 * n_pages if livecrawl else 0)
    return {"results": results, "cost_usd": round(cost, 4),
            "elapsed_ms": int((time.monotonic() - t0) * 1000)}


async def contents(urls: list[str], max_age: int = 86400) -> dict:
    """Fetch full page markdown for URLs already in hand (Search → Contents)."""
    t0 = time.monotonic()
    async with SEM["contents"]:
        body = await _post(f"{INDEX}/contents",
                           {"urls": urls, "formats": ["markdown", "metadata"],
                            "max_age": max_age}, timeout=120)
    pages = body if isinstance(body, list) else body.get("results", body.get("contents", []))
    return {"pages": pages, "cost_usd": round(COST[("contents", None)] * len(urls), 4),
            "elapsed_ms": int((time.monotonic() - t0) * 1000)}


async def balance() -> Optional[float]:
    """Account credit balance in USD, or None if the endpoint misbehaves."""
    try:
        async with httpx.AsyncClient(timeout=15) as cli:
            r = await cli.get(f"{API}/billing/account_balance",
                              headers={"X-API-Key": _key()})
        return round(r.json()["data"]["attributes"]["balance"] / 100, 2)
    except Exception:
        return None
