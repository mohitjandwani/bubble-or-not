"""Render Cron entrypoint: POST /rescore against the deployed API.
Cadence config lives server-side (probe TTLs decide what actually re-fetches)."""
import os

import httpx

url = os.environ["RESCORE_URL"]  # e.g. https://bubble-or-not.onrender.com/rescore
r = httpx.post(url, headers={"X-Admin-Key": os.environ["ADMIN_KEY"]}, timeout=30)
print(r.status_code, r.text[:200])
# 409 (already running) is a success for cron purposes
raise SystemExit(0 if r.status_code in (202, 409) else 1)
