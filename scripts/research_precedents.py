"""One-time (Pass 4): research the 1999 precedent for each of the 12 signatures
via one deep Research call → patch config/signatures.yaml with cited text.
Cost ≈ $0.10. Re-run only if signatures change. Human-verify the top rows.
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

CFG = ROOT / "config" / "signatures.yaml"

SCHEMA = {
    "type": "object",
    "properties": {"precedents": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "signature_id": {"type": "string"},
            "precedent_text": {"type": "string"},
            "precedent_date": {"type": ["string", "null"]},
            "citation_url": {"type": ["string", "null"]},
        },
        "required": ["signature_id", "precedent_text", "precedent_date", "citation_url"],
        "additionalProperties": False}}},
    "required": ["precedents"], "additionalProperties": False}


async def main() -> None:
    cfg = yaml.safe_load(CFG.read_text())
    sigs = cfg["signatures"]
    listing = "\n".join(f"- {s['id']}: {s['name']} — rule: {s['threshold_text']}"
                        for s in sigs)
    input_text = (
        "For each indicator below, find the closest documented 1999-2001 dot-com-era "
        "precedent: what happened, roughly when (YYYY-MM), and a citation URL from "
        "retrospective or contemporaneous coverage (news archives, Fed history pages, "
        "academic retrospectives). precedent_text must be ONE factual sentence <= 160 chars "
        "naming concrete numbers/dates where possible. Indicators:\n" + listing +
        "\nReturn one precedents[] entry per signature_id, exactly the ids given.")
    print("Researching (deep, ~1-3 min)...")
    resp = await youcom.research(input_text, effort="deep", output_schema=SCHEMA)
    got = {p["signature_id"]: p for p in resp["content"].get("precedents", [])}
    print(f"got {len(got)}/{len(sigs)} · cost ${resp['cost_usd']} · {resp['elapsed_ms']}ms")

    for s in sigs:
        p = got.get(s["id"])
        if p and p.get("precedent_text"):
            s["precedent_1999"] = p["precedent_text"][:200]
            s["precedent_citation_url"] = p.get("citation_url")
            print(f"  {s['id']}: {p['precedent_text'][:80]}... [{p.get('citation_url')}]")
        else:
            print(f"  {s['id']}: NOT RETURNED — keeping placeholder")

    CFG.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True, width=100))
    print(f"\npatched {CFG}")


asyncio.run(main())
