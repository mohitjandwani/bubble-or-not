"""Pass 0 smoke test — You.com API, both extraction patterns + balance.

Usage:
    python scripts/smoke_you.py balance
    python scripts/smoke_you.py a          # Pattern A: Research + output_schema + sec.gov lock
    python scripts/smoke_you.py b          # Pattern B: Finance Research + FINDING template

Each step prints raw-ish output so a human can eyeball the Pass 0 checklist:
- Pattern A: typed JSON (no prose), sec.gov URLs, nulls (not "") for unknowns
- Pattern B: markdown with `### FINDING` blocks, [[n]] markers, sources[]
"""
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
KEY = os.environ["YOU_API_KEY"]
HEADERS = {"X-API-Key": KEY}

# HANDOVER §9.1 verification query (counterparty side — where attribution lives).
COUNTERPARTY_QUERY = (
    "From CoreWeave's most recent 10-K or S-1 filing on sec.gov, extract: "
    "(1) percent of GPU/hardware supply sourced from NVIDIA (supplier concentration), "
    "(2) dollar value of purchase commitments to NVIDIA, "
    "(3) customer concentration (e.g. 'Customer A represents X% of revenue'), "
    "(4) any debt secured by GPU collateral. "
    "Quote the exact sentences from the filing and give the filing URLs. "
    "Populate the findings array with one entry per metric you looked for; if the "
    "numeric value is not stated, still emit the entry with value=null and the most "
    "relevant quote. Only return an empty findings array if the filings contain "
    "nothing about any of these topics."
)

# Schema per HANDOVER §2 output_schema rules: root object, every property required,
# unknowns nullable (so they come back null, never ""), additionalProperties false.
COUNTERPARTY_SCHEMA = {
    "type": "object",
    "properties": {
        "company": {"type": "string"},
        "filing_type": {"type": ["string", "null"]},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "enum": [
                            "supplier_concentration_pct",
                            "purchase_commitments_usd",
                            "customer_concentration_pct",
                            "gpu_collateralized_debt_usd",
                        ],
                    },
                    "value": {"type": ["number", "null"]},
                    "unit": {"type": ["string", "null"]},
                    "as_of": {"type": ["string", "null"]},
                    "quote": {"type": ["string", "null"]},
                    "source_url": {"type": ["string", "null"]},
                },
                "required": ["metric", "value", "unit", "as_of", "quote", "source_url"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["company", "filing_type", "findings"],
    "additionalProperties": False,
}

# HANDOVER §3 FINDING template, EVENT enum adapted to this call site's metrics.
FINDING_TEMPLATE = """

Answer using this exact structure. One block per finding:

### FINDING
- COMPANY: <name>
- METRIC: <one of: supplier_concentration_pct | purchase_commitments_usd | customer_concentration_pct | gpu_collateralized_debt_usd | none_found>
- DATE: <YYYY-MM-DD or "unknown">
- VALUE: <number + unit, or "n/a">
- QUOTE: "<exact sentence from the source>"
- CITATION: <[[n]] marker>

If nothing found, output one block with METRIC: none_found. No prose outside blocks.
"""

BALANCE_URL = "https://api.you.com/v1/billing/account_balance"


def balance() -> None:
    r = httpx.get(BALANCE_URL, headers=HEADERS, timeout=30)
    print(f"{BALANCE_URL} -> {r.status_code}")
    body = r.json()
    print(json.dumps(body, indent=2))
    try:
        cents = body["data"]["attributes"]["balance"]
        print(f"balance: ${cents / 100:,.2f}")
    except (KeyError, TypeError):
        pass


def pattern_a() -> None:
    payload = {
        "input": COUNTERPARTY_QUERY,
        "research_effort": "deep",
        "source_control": {"include_domains": ["sec.gov"]},
        "output_schema": COUNTERPARTY_SCHEMA,
    }
    print("POST /v1/research (deep, include_domains=sec.gov, output_schema) ...")
    t0 = time.time()
    r = httpx.post(
        "https://api.you.com/v1/research", headers=HEADERS, json=payload, timeout=900
    )
    elapsed = time.time() - t0
    print(f"status={r.status_code} elapsed={elapsed:.0f}s")
    if r.status_code != 200:
        print(r.text[:3000])
        sys.exit(1)
    body = r.json()
    out = body.get("output", body)
    content = out.get("content")
    print(f"content_type={out.get('content_type')}")
    parsed = json.loads(content) if isinstance(content, str) else content
    print("--- typed output ---")
    print(json.dumps(parsed, indent=2))
    sources = out.get("sources") or []
    print(f"--- sources ({len(sources)}) ---")
    for s in sources[:10]:
        print(" ", s.get("url", s))
    sec = [s for s in sources if "sec.gov" in str(s.get("url", ""))]
    print(f"sec.gov sources: {len(sec)}/{len(sources)}")


def pattern_b() -> None:
    payload = {
        "input": COUNTERPARTY_QUERY + FINDING_TEMPLATE,
        "research_effort": "deep",
    }
    print("POST /v1/finance_research (deep, FINDING template) ...")
    t0 = time.time()
    r = httpx.post(
        "https://api.you.com/v1/finance_research",
        headers=HEADERS,
        json=payload,
        timeout=900,
    )
    elapsed = time.time() - t0
    print(f"status={r.status_code} elapsed={elapsed:.0f}s")
    if r.status_code != 200:
        print(r.text[:3000])
        sys.exit(1)
    body = r.json()
    out = body.get("output", body)
    content = out.get("content") or ""
    print(f"content_type={out.get('content_type')}")
    print("--- markdown ---")
    print(content)
    blocks = content.count("### FINDING")
    marks = content.count("[[")
    sources = out.get("sources") or []
    print(f"--- FINDING blocks={blocks} [[n]] markers={marks} sources={len(sources)} ---")
    for s in sources[:10]:
        print(" ", s.get("url", s))


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "balance"
    {"balance": balance, "a": pattern_a, "b": pattern_b}[step]()
