"""Eval harness (agents-README §9): N back-to-back runs, then four checks —
score variance per factor (target σ<5), citation validity (sample URLs resolve
AND contain the claimed quote), extract-chain failure rate, cost per factor.

Usage:
  .venv/bin/python eval/run_eval.py            # analyze existing runs only
  .venv/bin/python eval/run_eval.py --runs 3   # trigger 3 fresh runs first (spends budget)
Writes a markdown report to eval/RESULTS.md and prints it.
"""
import argparse
import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=True)

import asyncpg  # noqa: E402

API = os.environ.get("EVAL_API", "http://localhost:8000")


async def trigger_runs(n: int) -> None:
    ak = os.environ["ADMIN_KEY"]
    async with httpx.AsyncClient(timeout=30) as cli:
        for i in range(n):
            r = await cli.post(f"{API}/rescore", headers={"X-Admin-Key": ak})
            run_id = r.json().get("run_id")
            print(f"run {i+1}/{n}: {run_id}", flush=True)
            while True:
                await asyncio.sleep(10)
                s = (await cli.get(f"{API}/state", params={"run_id": run_id})).json()
                if s.get("status") == "done":
                    print(f"  done · bti={s.get('bti')} cost=${s.get('total_cost')}")
                    break


async def analyze(sample_n: int = 10) -> str:
    con = await asyncpg.connect(os.environ["DATABASE_URL"])
    lines = ["# Eval results", ""]

    variance = await con.fetch("""
        WITH recent AS (SELECT run_id FROM runs WHERE status='done'
                        AND run_id LIKE 'run-%' ORDER BY started_at DESC LIMIT 3)
        SELECT factor, round(avg(score),1) AS mean,
               round(max(score)-min(score),1) AS spread,
               round(stddev_pop(score),2) AS sigma, count(*) AS n
        FROM factor_results WHERE run_id IN (SELECT run_id FROM recent)
        GROUP BY factor ORDER BY factor""")
    lines += ["## Score variance (last 3 done runs · target σ < 5)", "",
              "| factor | mean | max−min | σ | n |", "|---|---|---|---|---|"]
    for r in variance:
        flag = " ⚠" if (r["sigma"] or 0) >= 5 else ""
        lines.append(f"| {r['factor']} | {r['mean']} | {r['spread']} | {r['sigma']}{flag} | {r['n']} |")

    rows = await con.fetch("""
        SELECT quote, source_url FROM evidence
        WHERE source_url LIKE 'http%' AND quote IS NOT NULL AND length(quote) > 40
          AND run_id = (SELECT run_id FROM runs WHERE status='done'
                        AND run_id LIKE 'run-%' ORDER BY started_at DESC LIMIT 1)""")
    random.seed(42)
    sample = random.sample(rows, min(sample_n, len(rows)))
    ok_http = ok_claim = 0
    checked = []
    async with httpx.AsyncClient(timeout=20, follow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0"}) as cli:
        for r in sample:
            status, claim = "ERR", False
            try:
                resp = await cli.get(r["source_url"])
                status = resp.status_code
                if status == 200:
                    ok_http += 1
                    words = [w for w in r["quote"].split() if len(w) > 5][:6]
                    hits = sum(1 for w in words if w.lower() in resp.text.lower())
                    claim = hits >= max(2, len(words) // 2)
                    ok_claim += claim
            except Exception:
                pass
            checked.append((r["source_url"][:70], status, claim))
    lines += ["", f"## Citation validity (N={len(sample)}, seeded sample, latest run)", "",
              f"- HTTP 200: **{ok_http}/{len(sample)}**",
              f"- claimed text found on page: **{ok_claim}/{len(sample)}** "
              "(headless fetch — some valid pages block bots)", ""]
    for url, st, cl in checked:
        lines.append(f"  - `{st}` {'✓' if cl else '·'} {url}")

    stats = await con.fetch("""
        SELECT detail->'extract_stats' AS st FROM run_events
        WHERE detail ? 'extract_stats' AND run_id IN
          (SELECT run_id FROM runs WHERE status='done' ORDER BY started_at DESC LIMIT 3)""")
    tot = {"blocks": 0, "regex_ok": 0, "haiku_rescued": 0, "failed": 0}
    for r in stats:
        st = json.loads(r["st"]) if isinstance(r["st"], str) else (r["st"] or {})
        for k in tot:
            tot[k] += st.get(k, 0)
    if tot["blocks"]:
        lines += ["", "## Extract-chain (Pattern B, last 3 runs)", "",
                  f"- blocks: {tot['blocks']} · regex-parsed: {tot['regex_ok']} · "
                  f"Haiku-rescued: {tot['haiku_rescued']} · failed (excluded, visible): {tot['failed']}",
                  f"- failure rate: **{tot['failed']/tot['blocks']*100:.1f}%** · "
                  f"Haiku fallback rate: **{tot['haiku_rescued']/tot['blocks']*100:.1f}%**"]

    costs = await con.fetch("""
        SELECT factor, round(sum(cost)::numeric,3) AS usd FROM run_events
        WHERE cost > 0 AND run_id = (SELECT run_id FROM runs WHERE status='done'
                                     AND run_id LIKE 'run-%' ORDER BY started_at DESC LIMIT 1)
        GROUP BY factor ORDER BY usd DESC""")
    lines += ["", "## Cost per factor (latest run, uncached portions)", "",
              "| factor | $ |", "|---|---|"]
    for r in costs:
        lines.append(f"| {r['factor']} | {r['usd']} |")

    await con.close()
    report = "\n".join(lines) + "\n"
    (ROOT / "eval" / "RESULTS.md").write_text(report)
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=0)
    args = ap.parse_args()
    if args.runs:
        asyncio.run(trigger_runs(args.runs))
        time.sleep(2)
    print(asyncio.run(analyze()))
