"""Cold-start battery (battery doc §11 — MANDATORY before demo day).

Runs the full F3 battery once with WIDE windows (S1: month · S2: year) and
stores window-0 formation/destruction/intensity counts as the baselines that
every later run's CMI deltas compare against. No baseline = no delta = no
direction on demo day. Cost ≈ $0.60. Run: .venv/bin/python scripts/cold_start_f3.py
"""
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=True)

from schema import StatePayload  # noqa: E402
from agents.pg import PGStore  # noqa: E402
from agents.store import load_fixture_payload  # noqa: E402
from agents.f3_run import run_f3  # noqa: E402


async def main() -> None:
    store = PGStore()
    await store.init(os.environ["DATABASE_URL"])
    state, _ = load_fixture_payload()  # scratch state; baseline only writes caches
    run_id = f"coldstart-{datetime.now(timezone.utc):%m%d-%H%M%S}"

    async def emit(event_type: str, **kw) -> None:
        print(f"  {event_type:18} {kw.get('probe_id') or kw.get('factor') or ''} "
              f"{kw.get('detail') or ''}")

    print("Cold-start battery: S1 window=30d, S2 window=365d ...")
    cost = await run_f3(store, state, run_id, emit, baseline_mode=True)
    b1 = await store.cache_get("F3-baseline-s1", "window0", 24 * 365)
    b2 = await store.cache_get("F3-baseline-s2", "window0", 24 * 365)
    print(f"\nbaselines stored · cost ${cost:.2f}")
    print(f"  stage1 (month):  {b1}")
    print(f"  stage2 (year):   {b2}")


asyncio.run(main())
