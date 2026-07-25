"""Shared Pattern B extraction chain (HANDOVER §3) — written ONCE, used by every
Finance Research call site. The eval harness reports its failure rate.

Chain: regex-split `### FINDING` blocks → field parse → Haiku (temp 0) ONLY for
blocks regex couldn't parse → validate (one retry with the error appended) →
[[n]] → sources[n].url mapping → Finding objects.

Failure semantics: a block that still fails validation comes back with
ok=False (confidence=low, excluded from scoring, visible in trace) — never
dropped silently, never crashes the run.

Pass 0 lesson baked in: quotes that are crawl-error text ("could not be
accessed", "404") are rejected at validation, not scored as evidence.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional

import httpx
from pydantic import BaseModel, ValidationError, field_validator

FINDING_TEMPLATE = """

Answer using this exact structure. One block per finding:

### FINDING
- COMPANY: <name>
- EVENT: <one of: {enum}>
- DATE: <YYYY-MM-DD or "unknown">
- VALUE: <number + unit, or "n/a">
- QUOTE: "<exact sentence from the source>"
- CITATION: <[[n]] marker>

If nothing found, output one block with EVENT: none_found. No prose outside blocks.
"""

HAIKU_SYSTEM = """You extract structured facts from a finance research report.
Rules:
- Use ONLY facts present in the provided text. Never infer or add outside knowledge.
- Copy the [[n]] citation marker that appears with each fact into the citation field.
- If a field is not stated, output null. Never guess a number or date.
- Output JSON matching the schema exactly. No prose."""

_CRAWL_ERROR = re.compile(
    r"could not be accessed|404|error retrieving|unable to (?:access|retrieve)|"
    r"page (?:was )?not found|failed to (?:fetch|load)", re.I)
_FIELD = re.compile(r"^\s*-\s*(COMPANY|EVENT|DATE|VALUE|QUOTE|CITATION)\s*:\s*(.*)$",
                    re.I | re.M)
_CITE = re.compile(r"\[\[(\d+)\]\]")


class Finding(BaseModel):
    company: str
    event: str
    date: Optional[str] = None      # YYYY-MM-DD or None
    value: Optional[str] = None     # free text "number + unit"
    quote: str
    citation_n: Optional[int] = None
    source_url: Optional[str] = None

    @field_validator("quote")
    @classmethod
    def quote_is_real(cls, v: str) -> str:
        v = v.strip().strip('"“”')
        if len(v) < 10:
            raise ValueError("quote too short to be an exact source sentence")
        if _CRAWL_ERROR.search(v):
            raise ValueError("quote is crawl-error text, not source content")
        return v

    @field_validator("date", mode="before")
    @classmethod
    def date_or_none(cls, v):
        if v is None:
            return None
        v = str(v).strip().strip('"')
        return v if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else None


@dataclass
class ExtractResult:
    findings: list[Finding] = field(default_factory=list)
    failed_blocks: list[str] = field(default_factory=list)  # visible in trace
    stats: dict = field(default_factory=dict)


def _parse_block(block: str, allowed_events: list[str]) -> Finding:
    fields = {m.group(1).upper(): m.group(2).strip() for m in _FIELD.finditer(block)}
    if not fields.get("COMPANY") or not fields.get("EVENT"):
        raise ValueError(f"missing COMPANY/EVENT in block: {block[:80]!r}")
    event = fields["EVENT"].strip().strip('"').lower()
    if event not in allowed_events:
        raise ValueError(f"event {event!r} not in {allowed_events}")
    cite = _CITE.search(fields.get("CITATION", "") or block)
    value = fields.get("VALUE", "").strip()
    return Finding(
        company=fields["COMPANY"].strip('"'),
        event=event,
        date=fields.get("DATE", "").strip() or None,
        value=None if value.lower() in ("n/a", "", "none", "unknown") else value,
        quote=fields.get("QUOTE", ""),
        citation_n=int(cite.group(1)) if cite else None,
    )


def _haiku_block(block: str, allowed_events: list[str], error: str = "") -> dict:
    """Rescue ONE failed block via Haiku, temp 0. Context = the block only."""
    schema_desc = {"company": "string", "event": f"one of {allowed_events} or null",
                   "date": "YYYY-MM-DD or null", "value": "string or null",
                   "quote": "exact sentence, string", "citation_n": "integer from [[n]] or null"}
    user = f"Text:\n{block}\n\nTarget JSON schema: {json.dumps(schema_desc)}"
    if error:
        user += f"\n\nA previous attempt failed validation with: {error}. Fix that."
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                 "anthropic-version": "2023-06-01"},
        json={"model": "claude-haiku-4-5-20251001", "max_tokens": 500, "temperature": 0,
              "system": HAIKU_SYSTEM,
              "messages": [{"role": "user", "content": user}]},
        timeout=60)
    r.raise_for_status()
    text = r.json()["content"][0]["text"]
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("haiku returned no JSON object")
    return json.loads(m.group(0))


def extract(markdown: str, sources: list[dict], allowed_events: list[str]) -> ExtractResult:
    """THE shared chain. `allowed_events` comes from the call site's event enum
    (always include 'none_found')."""
    res = ExtractResult(stats={"blocks": 0, "regex_ok": 0, "haiku_rescued": 0, "failed": 0,
                               "none_found": 0})
    # Drop ONLY the preamble before the first marker. Everything after a marker
    # is a block — even ones regex can't field-parse (those are Haiku's job).
    segments = re.split(r"###\s*FINDING", markdown)
    blocks = [b.strip() for b in segments[1:] if b.strip()]
    res.stats["blocks"] = len(blocks)

    for block in blocks:
        finding: Finding | None = None
        try:
            finding = _parse_block(block, allowed_events)
            res.stats["regex_ok"] += 1
        except (ValueError, ValidationError) as first_err:
            try:  # Haiku fallback, one validation retry with the error appended
                raw = _haiku_block(block, allowed_events)
                try:
                    raw["event"] = (raw.get("event") or "").lower()
                    finding = Finding(**{k: raw.get(k) for k in Finding.model_fields})
                except ValidationError as ve:
                    raw = _haiku_block(block, allowed_events, error=str(ve)[:300])
                    raw["event"] = (raw.get("event") or "").lower()
                    finding = Finding(**{k: raw.get(k) for k in Finding.model_fields})
                if finding.event not in allowed_events:
                    raise ValueError(f"event {finding.event!r} not in enum")
                res.stats["haiku_rescued"] += 1
            except Exception as exc:
                res.stats["failed"] += 1
                res.failed_blocks.append(f"{block[:200]} | error: {str(first_err)[:120]} / {str(exc)[:120]}")
                continue

        if finding.event == "none_found":
            res.stats["none_found"] += 1
            continue  # typed empty answer — countable, not evidence
        if finding.citation_n and 0 < finding.citation_n <= len(sources):
            src = sources[finding.citation_n - 1]
            finding.source_url = src.get("url") if isinstance(src, dict) else str(src)
        res.findings.append(finding)
    return res
