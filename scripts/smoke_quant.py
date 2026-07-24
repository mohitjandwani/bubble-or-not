"""Pass 0 smoke test — quant data plane (yfinance + FMP).

- yfinance: ^IXIC both eras (1996-2001 amber, 2023-now bright), ^TNX today
- FMP (if FMP_API_KEY set): S&P 500 constituents + fed funds indicator
"""
import os
from pathlib import Path

import yfinance as yf
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)


def show(label, df):
    print(f"\n=== {label} — {len(df)} rows ===")
    if len(df):
        print(df.head(2).to_string())
        print("...")
        print(df.tail(2).to_string())


ixic_99 = yf.download("^IXIC", start="1996-01-01", end="2001-12-31", progress=False)
show("^IXIC 1996-2001 (benchmark era)", ixic_99)

ixic_now = yf.download("^IXIC", start="2023-01-01", progress=False)
show("^IXIC 2023-now (current era)", ixic_now)

tnx = yf.download("^TNX", period="1mo", progress=False)
show("^TNX last month (10Y yield, quant strip card 4)", tnx)

fmp_key = os.environ.get("FMP_API_KEY", "")
if not fmp_key:
    print("\n=== FMP: SKIPPED (no FMP_API_KEY in .env) ===")
    print("Needed in Pass 2 for: S&P constituents (top-10 weight, %>200dma), federalFunds.")
else:
    import httpx

    r = httpx.get(
        "https://financialmodelingprep.com/api/v3/sp500_constituent",
        params={"apikey": fmp_key},
        timeout=30,
    )
    data = r.json()
    print(f"\n=== FMP sp500_constituent: {r.status_code}, {len(data)} names ===")
    print(data[:3])
    r = httpx.get(
        "https://financialmodelingprep.com/api/v4/economic",
        params={"name": "federalFunds", "apikey": fmp_key},
        timeout=30,
    )
    print(f"=== FMP federalFunds: {r.status_code} ===")
    print(r.json()[:3] if r.status_code == 200 else r.text[:500])
