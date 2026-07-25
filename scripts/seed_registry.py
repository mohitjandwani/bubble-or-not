"""One-time: research the known-deal registry (~12 edges) via one deep
Research call with typed schema → data/registry/edges.yaml → registry_edges table.
Statuses start announced_only; S2-Q2 counterparty verification upgrades to verified.
"""
import asyncio
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=True)

from agents import youcom  # noqa: E402

OUT = ROOT / "data" / "registry" / "edges.yaml"

SCHEMA = {
    "type": "object",
    "properties": {"edges": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "from_entity": {"type": "string"},
            "to_entity": {"type": "string"},
            "archetype": {"type": "string", "enum": ["A", "B", "C", "D", "E", "F"]},
            "amount_usd_m": {"type": ["number", "null"]},
            "announced_date": {"type": ["string", "null"]},
            "source_url": {"type": ["string", "null"]},
            "note": {"type": ["string", "null"]},
        },
        "required": ["from_entity", "to_entity", "archetype", "amount_usd_m",
                     "announced_date", "source_url", "note"],
        "additionalProperties": False}}},
    "required": ["edges"], "additionalProperties": False}

INPUT = """List the major ANNOUNCED circular-financing relationships in the AI \
infrastructure complex, one edge per relationship, with press citations. Archetypes:
A = chip vendor invests equity in a customer that buys its products (e.g. NVIDIA -> neoclouds)
B = vendor guarantees/backstops to rent back unused capacity from a customer
C = compute-for-equity triangle (chip vendor / cloud provider equity in an AI lab paired \
with compute purchase commitments, e.g. Microsoft-OpenAI, Amazon-Anthropic, Google-Anthropic, \
NVIDIA-OpenAI, OpenAI-Oracle)
D = GPU-collateralized debt facilities to neoclouds (private credit lending against GPUs)
E = SPV / joint-venture datacenter structures keeping capacity commitments off balance sheet
F = AI lab invests in startups (or grants credits) that are also its paying API customers \
(OpenAI Startup Fund portfolio, Anthropic-backed startups)

Cover: NVIDIA<->CoreWeave, NVIDIA<->Nebius or other neoclouds, the big lab-cloud pairs, \
at least one GPU-backed debt facility, at least one datacenter SPV/JV, and 2-3 lab->startup \
fund edges with named startups. amount_usd_m = announced dollar size in MILLIONS (null if \
undisclosed). announced_date = YYYY-MM-DD or YYYY-MM. source_url = a press article URL \
naming the deal. 10-15 edges total, most recent announcements preferred."""


async def main() -> None:
    print("Researching registry (deep, ~1-3 min)...")
    resp = await youcom.research(INPUT, effort="deep", output_schema=SCHEMA)
    edges = resp["content"].get("edges", [])
    print(f"got {len(edges)} edges · cost ${resp['cost_usd']}")
    for i, e in enumerate(edges):
        e["edge_id"] = f"edge-{e['archetype']}-{i:02d}"
        e["status"] = "announced_only"
        print(f"  [{e['archetype']}] {e['from_entity']} -> {e['to_entity']} "
              f"${e.get('amount_usd_m')}M {e.get('announced_date')} | {(e.get('source_url') or '')[:60]}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(yaml.safe_dump({"edges": edges}, sort_keys=False, allow_unicode=True, width=110))
    print(f"wrote {OUT}")


asyncio.run(main())
