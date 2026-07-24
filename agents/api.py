"""FastAPI backend — the five-endpoint contract from agents-README §7.
Pass 2: Postgres store when DATABASE_URL is set (in-memory fallback for
DB-less dev), pipeline with real quant factors.

Run:  .venv/bin/uvicorn agents.api:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from schema import RescoreResponse
from agents import store as store_mod
from agents.pg import PGStore
from agents.pipeline import apply_real_hero, run_pipeline

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

app = FastAPI(title="Bubble or Not — evidence engine", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_rescore_lock = asyncio.Lock()


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
            await run_pipeline()

    asyncio.create_task(guarded())
    for _ in range(50):
        state = await store_mod.STORE.state()
        if state and state.status == "running":
            return RescoreResponse(run_id=state.run_id, status="running")
        await asyncio.sleep(0.02)
    return RescoreResponse(run_id="pending", status="running")


@app.get("/healthz")
async def healthz():
    return {"ok": True, "store": type(store_mod.STORE).__name__}
