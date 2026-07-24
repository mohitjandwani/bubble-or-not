"""Pass 2 — pull the real hero-chart series into /data/benchmarks/.

- ^IXIC 1996-01→2001-12 and 2023-01→now, weekly close, indexed to 100 at era start
- Fed funds effective (FMP economic indicator), both eras, as change-from-cycle-start
Run whenever you want fresher data; the backend reads these files at startup and
refreshes the live tail during runs (Pass 2 keeps it file-based — cheap and cached).
"""
import json
import os
import sys
from pathlib import Path

import httpx
import yfinance as yf
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=True)

OUT = ROOT / "data" / "benchmarks"
OUT.mkdir(parents=True, exist_ok=True)


def weekly_indexed(ticker: str, start: str, end: str | None) -> list[dict]:
    df = yf.download(ticker, start=start, end=end, interval="1wk", progress=False)
    closes = df["Close"].iloc[:, 0] if hasattr(df["Close"], "columns") else df["Close"]
    closes = closes.dropna()
    base = float(closes.iloc[0])
    return [{"t": idx.strftime("%Y-%m-%d"), "v": round(float(v) / base * 100, 2)}
            for idx, v in closes.items()]


era_1999 = weekly_indexed("^IXIC", "1996-01-01", "2002-01-01")
era_now = weekly_indexed("^IXIC", "2023-01-01", None)
(OUT / "ixic_1996_2001.json").write_text(json.dumps(era_1999))
(OUT / "ixic_now.json").write_text(json.dumps(era_now))
peak = max(era_1999, key=lambda p: p["v"])
print(f"1999 era: {len(era_1999)} wk pts, peak {peak['v']} on {peak['t']}")
print(f"now era:  {len(era_now)} wk pts, last {era_now[-1]['v']} on {era_now[-1]['t']}")

fmp_key = os.environ.get("FMP_API_KEY", "")
if fmp_key:
    r = httpx.get("https://financialmodelingprep.com/api/v4/economic",
                  params={"name": "federalFunds", "from": "1995-01-01", "apikey": fmp_key},
                  timeout=30)
    rows = sorted(r.json(), key=lambda x: x["date"])
    (OUT / "fedfunds.json").write_text(json.dumps(rows))
    print(f"fedfunds: {len(rows)} monthly pts, {rows[0]['date']}..{rows[-1]['date']}")
else:
    print("fedfunds: SKIPPED (no FMP key)")

meta = {"peak_date_1999": peak["t"], "fetched_at_note": "regenerate via scripts/fetch_benchmarks.py"}
(OUT / "meta.json").write_text(json.dumps(meta))
print("meta:", meta)
