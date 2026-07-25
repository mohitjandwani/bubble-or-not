"""FastAPI backend — the five-endpoint contract from agents-README §7.
Pass 2: Postgres store when DATABASE_URL is set (in-memory fallback for
DB-less dev), pipeline with real quant factors.

Run:  .venv/bin/uvicorn agents.api:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from schema import RescoreResponse, RunEvent
from agents import store as store_mod
from agents.pg import PGStore
from agents.pipeline import apply_real_hero, run_pipeline

# Ceiling for one whole run. The per-factor guards in pipeline.py sum to at most
# TIMEOUTS["quant"] + max(the parallel factor timeouts) = 240 + 600; this leaves
# slack for finalization. Backstop only — if it ever fires, a per-factor guard
# failed to do its job.
RUN_BUDGET_S = 1080

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

app = FastAPI(title="Bubble or Not — evidence engine", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_rescore_lock = asyncio.Lock()


async def _finalize_orphan(reason: str) -> str | None:
    """Never leave a run at status='running' when nothing is driving it.

    An orphan is unrecoverable and self-perpetuating: the SPA polls /state every
    2s while status is 'running', so the page pins to a run that will never
    finish, and every later POST /rescore is refused with 409 until the process
    restarts. Runs are orphaned whenever the instance is replaced mid-flight —
    routine on Render's free tier, which is exactly where this bit us.

    Factor scores are left untouched: they already hold last-good values, which
    is the stale-not-blank contract, and each carries its own `as_of` so the UI
    can show how old it is.
    """
    state = await store_mod.STORE.state()
    if state is None or state.status != "running":
        return None
    state.status = "done"
    state.updated_at = datetime.now(timezone.utc)
    await store_mod.STORE.put_state(state)
    await store_mod.STORE.emit(RunEvent(
        id=0, run_id=state.run_id, ts=datetime.now(timezone.utc),
        event_type="run.completed",
        detail={"partial": True, "reason": reason,
                "note": "finalized without completing every factor"}))
    return state.run_id


@app.on_event("startup")
async def startup() -> None:
    dsn = os.environ.get("DATABASE_URL", "")
    if dsn:
        pg = PGStore()
        await pg.init(dsn)
        store_mod.set_store(pg)
    if not await store_mod.STORE.has_runs():
        state, rows = store_mod.load_fixture_payload()
        apply_real_hero(state)  # real benchmark series even on the seed run
        await store_mod.STORE.put_state(state)
        await store_mod.STORE.put_evidence(state.run_id, rows)
    # This process is new, so any run still marked 'running' belongs to a dead one.
    orphan = await _finalize_orphan("process restarted mid-run")
    if orphan:
        print(f"[startup] finalized orphaned run {orphan}", flush=True)


@app.get("/state")
async def get_state(run_id: str | None = Query(default=None)):
    state = await store_mod.STORE.state(run_id)
    if state is None:
        raise HTTPException(404, detail=f"unknown run_id {run_id!r}")
    return state


@app.get("/events")
async def get_events(since: int = Query(default=0, ge=0)):
    events = await store_mod.STORE.events_since(since)
    return {"events": events, "last_id": events[-1].id if events else since}


@app.get("/evidence/{factor}")
async def get_evidence(factor: str, run_id: str | None = Query(default=None)):
    if factor not in {"f1", "f2", "f3", "f4", "f5", "f6"}:
        raise HTTPException(404, detail="unknown factor")
    return await store_mod.STORE.evidence_for(factor, run_id)


@app.post("/rescore", response_model=RescoreResponse, status_code=202)
async def rescore(x_admin_key: str = Header(default="")):
    if x_admin_key != os.environ.get("ADMIN_KEY", ""):
        raise HTTPException(401, detail="bad admin key")
    if _rescore_lock.locked():
        raise HTTPException(409, detail="a run is already active")

    async def guarded() -> None:
        async with _rescore_lock:
            try:
                await asyncio.wait_for(run_pipeline(), RUN_BUDGET_S)
            except Exception as exc:
                # Backstop for anything the per-factor guards miss. Without this
                # the run stays 'running' forever and the 409 above locks out
                # every future rescore for the life of the process.
                await _finalize_orphan(f"run watchdog: {type(exc).__name__}")

    asyncio.create_task(guarded())
    for _ in range(50):
        state = await store_mod.STORE.state()
        if state and state.status == "running":
            return RescoreResponse(run_id=state.run_id, status="running")
        await asyncio.sleep(0.02)
    return RescoreResponse(run_id="pending", status="running")


@app.get("/engine")
async def engine():
    """Screen 2 payload: the literal You.com usage map + live balance +
    per-probe last-run stats from the trace."""
    from agents import youcom
    from agents.registry import PROBE_REGISTRY

    stats: dict[str, dict] = {}
    pg = getattr(store_mod.STORE, "pool", None)
    if pg is not None:
        async with pg.acquire() as con:
            rows = await con.fetch("""
                SELECT DISTINCT ON (probe_id) probe_id, cost, elapsed_ms, cache_hit,
                       ts, endpoint
                FROM run_events WHERE event_type='agent.tool_call' AND probe_id IS NOT NULL
                ORDER BY probe_id, id DESC""")
        for r in rows:
            stats[r["probe_id"]] = {
                "last_cost": float(r["cost"]) if r["cost"] is not None else None,
                "last_elapsed_ms": r["elapsed_ms"], "cache_hit": r["cache_hit"],
                "last_ts": r["ts"].isoformat()}
    bal = await youcom.balance()
    return {"probes": PROBE_REGISTRY, "balance_usd": bal, "probe_stats": stats,
            "pricing_note": "search $0.005 · research std $0.05 / deep $0.10 · "
                            "finance_research deep $0.11 · contents $0.001/pg"}


@app.get("/healthz")
async def healthz():
    return {"ok": True, "store": type(store_mod.STORE).__name__}


# Prod: the built SPA is served same-origin from /. Mounted LAST so the API
# routes above win; html=True gives SPA index fallback. Local dev keeps Vite.
_DIST = Path(__file__).resolve().parents[1] / "dashboard" / "dist"
if _DIST.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="spa")
