# Eval results

## Score variance (last 3 done runs · target σ < 5)

| factor | mean | max−min | σ | n |
|---|---|---|---|---|
| f1 | 31.4 | 4.4 | 2.07 | 3 |
| f2 | 30.8 | 21.4 | 9.11 ⚠ | 3 |
| f3 | 29.3 | 5.0 | 2.36 | 3 |
| f4 | 55.6 | 25.0 | 10.39 ⚠ | 3 |
| f5 | 36.6 | 0.0 | 0.00 | 3 |
| f6 | 100.0 | 0.0 | 0.00 | 3 |

## Citation validity (N=10, seeded sample, latest run)

- HTTP 200: **7/10**
- claimed text found on page: **5/10** (headless fetch — some valid pages block bots)

  - `200` ✓ https://www.sec.gov/Archives/edgar/data/1769628/000176962826000129/crw
  - `200` ✓ https://finance.yahoo.com/quote/RSP
  - `200` ✓ https://www.marketscreener.com/news/nvidia-quarterly-report-for-quarte
  - `403` · https://www.investing.com/news/transcripts/earnings-call-transcript-nv
  - `403` · https://www.investing.com/news/transcripts/earnings-call-transcript-nv
  - `200` ✓ https://www.federalreserve.gov/newsevents/speech/bowman20260713a.htm
  - `200` · https://s201.q4cdn.com/141608511/files/doc_financials/2027/q1/NVDA-Q1-
  - `200` ✓ https://www.federalreserve.gov/newsevents/speech/jefferson20260716a1.h
  - `403` · https://www.investing.com/news/transcripts/earnings-call-transcript-nv
  - `200` · https://graphvest.com/nvda-nvidia-earnings-blackwell-data-center

## Extract-chain (Pattern B, last 3 runs)

- blocks: 45 · regex-parsed: 45 · Haiku-rescued: 0 · failed (excluded, visible): 0
- failure rate: **0.0%** · Haiku fallback rate: **0.0%**

## Cost per factor (last 3 runs, uncached portions)

| factor | $ |
|---|---|
| f3 | 1.385 |
| f2 | 1.340 |
| f4 | 0.330 |
| f6 | 0.315 |
| f1 | 0.135 |

## Notes (read with the table)

- Runs were INDEPENDENT pulls (probe caches cleared between runs, baselines preserved).
  Back-to-back cached rescores are reproducible by construction (σ=0).
- BTI across the 3 pulls: 36.6 / 32.7 / 37.2 — headline stable within ~4.5 pts.
- f2/f4 ⚠: both source findings from Finance Research, which surfaces different
  documents per pull. Caching pins them within a demo day; variance is visible, not hidden.
- f6=100 was a small-sample artifact (only 10 classifiable articles → density 0.50);
  fixed post-eval with a text-quality filter + low_coverage flag under 20 articles.
- Citation misses are bot-walls (investing.com 403s); sec.gov / federalreserve.gov /
  yahoo all verify with the claimed text present.
