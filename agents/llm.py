"""Local LLM layer — Haiku, temperature 0, JSON out. The middle intelligence
layer from agents-README §1: bounded, rubric-anchored judgment. It never does
scoring math and never sees the open web — only text we hand it.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

import httpx

MODEL = "claude-haiku-4-5-20251001"
_SEM = asyncio.Semaphore(8)


async def haiku_json(system: str, user: str, max_tokens: int = 1000) -> Any:
    """One rubric call → parsed JSON. One retry on transport/parse failure."""
    last: Exception | None = None
    for attempt in range(2):
        try:
            async with _SEM, httpx.AsyncClient(timeout=90) as cli:
                r = await cli.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                             "anthropic-version": "2023-06-01"},
                    json={"model": MODEL, "max_tokens": max_tokens, "temperature": 0,
                          "system": system,
                          "messages": [{"role": "user", "content": user}]})
            r.raise_for_status()
            text = r.json()["content"][0]["text"]
            m = re.search(r"\[.*\]|\{.*\}", text, re.S)
            if not m:
                raise ValueError(f"no JSON in response: {text[:120]!r}")
            return json.loads(m.group(0))
        except Exception as exc:
            last = exc
            if attempt == 0:
                await asyncio.sleep(1)
    raise last


RHETORIC_SYSTEM = """Score this Federal Reserve speech on hawkishness, -1.0 to +1.0.
Anchors:
 +1.0  explicit signal of further tightening; inflation framed as primary risk
 +0.5  concern about inflation persistence, no commitment
  0.0  balanced risks, data-dependent, no directional lean
 -0.5  concern about labor market softening or growth
 -1.0  explicit signal of easing

Output JSON: {"score": float, "evidence_quote": "<one sentence justifying the score>"}
Score the language used, not your view of policy. Ignore boilerplate."""

TONE_SYSTEM = """Score management's guidance confidence 0-10.
 9-10 raised guidance with specific numeric targets
 7-8  maintained with confident, specific language
 5-6  maintained with vague or qualified language
 3-4  hedged, wide ranges, deferred specifics
 0-2  lowered or withdrew guidance

Output JSON: {"score": int, "hedging_phrases": [str], "quote": str}"""

HYPE_SYSTEM = """For each article, identify bubble-narrative markers:
 new_paradigm | this_time_different | infinite_demand |
 profitless_growth_celebrated | price_target_leapfrog | fomo_framing

Mark a marker present ONLY if the article asserts it, not if it quotes someone
skeptically or reports that others believe it.

Output JSON: [{"url": str, "markers": [str], "quote": str|null}]"""
