"""QUANT probes — F5 breadth + F1 rates. Pure math over FMP/yfinance.
No LLM anywhere in this file; that's the point of the row it feeds.

All functions are synchronous (yfinance blocks); the pipeline wraps them in
asyncio.to_thread. Results cache to data/cache/quant-<date>.json so dev
iterations don't hammer FMP (the probe_cache table takes over on Render).
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
FMP = "https://financialmodelingprep.com"


def norm(x: float, lo: float, hi: float) -> float:
    """Clamp-normalize to 0..1 (methodology doc)."""
    if hi == lo:
        return 0.0
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def _fmp_key() -> str:
    return os.environ.get("FMP_API_KEY", "")


def _monthly_tail(series, n: int = 12) -> list[float]:
    """Last close of each month, trailing n months, rounded."""
    by_month = series.resample("ME").last().dropna()
    return [round(float(v), 2) for v in by_month.tail(n)]


# --------------------------------------------------------------------- probes
def top10_weight() -> dict:
    """Top-10 S&P 500 weight from FMP constituents + batch quotes."""
    with httpx.Client(timeout=30) as cli:
        names = cli.get(f"{FMP}/api/v3/sp500_constituent",
                        params={"apikey": _fmp_key()}).json()
        symbols = [n["symbol"] for n in names]
        caps: dict[str, float] = {}
        for i in range(0, len(symbols), 100):
            batch = cli.get(f"{FMP}/api/v3/quote/{','.join(symbols[i:i+100])}",
                            params={"apikey": _fmp_key()}).json()
            for q in batch:
                if q.get("marketCap"):
                    caps[q["symbol"]] = q["marketCap"]
    total = sum(caps.values())
    top = sorted(caps.values(), reverse=True)[:10]
    return {"value": round(sum(top) / total * 100, 2), "coverage": len(caps),
            "source": "fmp", "url": f"{FMP}/api/v3/sp500_constituent"}


def spy_rsp_gap() -> dict:
    """SPY − RSP trailing-6m return gap (pp) + monthly sparkline of that gap."""
    px = yf.download(["SPY", "RSP"], period="19mo", interval="1d", progress=False)["Close"].dropna()
    ret6 = px / px.shift(126) - 1  # ~126 trading days = 6m
    gap = (ret6["SPY"] - ret6["RSP"]) * 100
    return {"value": round(float(gap.dropna().iloc[-1]), 2),
            "sparkline": _monthly_tail(gap.dropna()),
            "source": "yfinance", "url": "https://finance.yahoo.com/quote/RSP"}


def pct_above_200dma() -> dict:
    """% of S&P constituents above their 200dma. Bulk yfinance download;
    NaN columns dropped, coverage reported (honesty over completeness)."""
    with httpx.Client(timeout=30) as cli:
        names = cli.get(f"{FMP}/api/v3/sp500_constituent",
                        params={"apikey": _fmp_key()}).json()
    symbols = [n["symbol"].replace(".", "-") for n in names]
    px = yf.download(symbols, period="11mo", interval="1d", progress=False,
                     threads=True)["Close"]
    px = px.dropna(axis=1, thresh=150)
    dma = px.rolling(200, min_periods=150).mean()
    last, last_dma = px.iloc[-1], dma.iloc[-1]
    mask = ~(last.isna() | last_dma.isna())
    above = (last[mask] > last_dma[mask])
    hist = (px > dma).sum(axis=1) / (~px.isna()).sum(axis=1) * 100
    return {"value": round(float(above.mean() * 100), 1), "coverage": int(mask.sum()),
            "sparkline": _monthly_tail(hist.dropna()),
            "source": "yfinance", "url": "https://finance.yahoo.com/quote/%5EGSPC"}


def tnx_yield() -> dict:
    px = yf.download("^TNX", period="13mo", interval="1d", progress=False)["Close"]
    series = px.iloc[:, 0] if hasattr(px, "columns") else px
    series = series.dropna()
    return {"value": round(float(series.iloc[-1]), 2),
            "sparkline": _monthly_tail(series),
            "source": "yfinance", "url": "https://finance.yahoo.com/quote/%5ETNX"}


def rates_path() -> dict:
    """F1 rate sub-metrics from FMP: EFFR (economic indicator) + 1Y treasury.
    steepness_bp = (1Y yield − EFFR) × 100 — a futures-free proxy for the
    12-month implied path. P(hike) / time-to-tightening need futures → no-data."""
    with httpx.Client(timeout=30) as cli:
        eff = cli.get(f"{FMP}/api/v4/economic",
                      params={"name": "federalFunds", "apikey": _fmp_key()}).json()
        effr = float(sorted(eff, key=lambda x: x["date"])[-1]["value"])
        tre = cli.get(f"{FMP}/api/v4/treasury",
                      params={"from": str(date.today().replace(day=1)),
                              "to": str(date.today()), "apikey": _fmp_key()}).json()
        year1 = float(sorted(tre, key=lambda x: x["date"])[-1]["year1"]) if tre else None
    steep = round((year1 - effr) * 100, 0) if year1 is not None else None
    return {"effr": effr, "year1": year1, "steepness_bp": steep,
            "source": "fmp", "url": f"{FMP}/api/v4/treasury"}


# --------------------------------------------------------------------- scoring
def f5_score(m: dict) -> float:
    """Methodology F5 with renormalization over available sub-metrics
    (hl_spread has no allowed source → its 0.15 weight redistributes)."""
    parts = [
        (0.30, norm(m["top10_weight_pct"], 25, 42)),
        (0.30, norm(m["spy_minus_rsp_6m_pp"], 0, 12)),
        (0.25, 1 - norm(m["pct_above_200dma"], 30, 75)),
        # 0.15 · hl_spread — no-data
    ]
    w = sum(p[0] for p in parts)
    return round(100 * sum(wi * v for wi, v in parts) / w, 1)


def f1_rates_score(m: dict) -> float | None:
    """Partial F1 — only the rate-derived sub-metrics exist in Pass 2.
    Rhetoric (0.20) arrives in Pass 4; P(hike)/time-to-tightening/real-rate
    have no futures/TIPS source → factor stays low_coverage until then."""
    if m.get("steepness_bp") is None:
        return None
    return round(100 * norm(m["steepness_bp"], 0, 200), 1)


def compute_quant(use_cache: bool = True) -> dict:
    """All quant probes, file-cached per day."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE / f"quant-{date.today()}.json"
    if use_cache and cache_file.exists():
        out = json.loads(cache_file.read_text())
        out["cache_hit"] = True
        return out

    t10, gap, dma, tnx, rates = top10_weight(), spy_rsp_gap(), pct_above_200dma(), tnx_yield(), rates_path()
    sub = {
        "top10_weight_pct": t10["value"],
        "spy_minus_rsp_6m_pp": gap["value"],
        "pct_above_200dma": dma["value"],
        "tnx_yield": tnx["value"],
        "constituent_coverage": dma["coverage"],
    }
    out = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "probes": {"top10": t10, "gap": gap, "dma200": dma, "tnx": tnx, "rates": rates},
        "f5_sub_metrics": sub,
        "f5_score": f5_score(sub),
        "f1_sub_metrics": {"path_steepness_bp": rates["steepness_bp"],
                           "effr": rates["effr"], "year1": rates["year1"]},
        "f1_rates_score": f1_rates_score(rates),
        "cache_hit": False,
    }
    cache_file.write_text(json.dumps(out))
    return out


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
    result = compute_quant(use_cache="--fresh" not in os.sys.argv)
    print(json.dumps({k: v for k, v in result.items() if k != "probes"}, indent=2))
