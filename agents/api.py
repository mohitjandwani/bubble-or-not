"""FastAPI backend — the five-endpoint contract from agents-README §7.
Pass 1: in-memory store + fake pipeline. The endpoint surface never changes again.

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
from agents.store import STORE
from agents.fake_pipeline import run_fake_pipeline

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

app = FastAPI(title="Bubble or Not — evidence engine", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_rescore_lock = asyncio.Lock()


@app.on_event("startup")
async def seed() -> None:
    STORE.load_fixtures()


@app.get("/state")
async def get_state(run_id: str | None = Query(default=None)):
    state = STORE.state(run_id)
    if state is None:
        raise HTTPException(404, detail=f"unknown run_id {run_id!r}")
    return state


@app.get("/events")
async def get_events(since: int = Query(default=0, ge=0)):
    events = STORE.events_since(since)
    return {"events": events, "last_id": events[-1].id if events else since}


@app.get("/evidence/{factor}")
async def get_evidence(factor: str, run_id: str | None = Query(default=None)):
    if factor not in {"f1", "f2", "f3", "f4", "f5", "f6"}:
        raise HTTPException(404, detail="unknown factor")
    return STORE.evidence_for(factor, run_id)


@app.post("/rescore", response_model=RescoreResponse, status_code=202)
async def rescore(x_admin_key: str = Header(default="")):
    if x_admin_key != os.environ.get("ADMIN_KEY", ""):
        raise HTTPException(401, detail="bad admin key")
    if _rescore_lock.locked():
        raise HTTPException(409, detail="a run is already active")

    async def guarded() -> None:
        async with _rescore_lock:
            await run_fake_pipeline()

    task = asyncio.create_task(guarded())
    # give the pipeline a beat to register the running state so we can return its id
    for _ in range(50):
        state = STORE.state()
        if state and state.status == "running":
            return RescoreResponse(run_id=state.run_id, status="running")
        await asyncio.sleep(0.02)
    return RescoreResponse(run_id=STORE.current_run_id or "", status="running")


@app.get("/healthz")
async def healthz():
    return {"ok": True, "runs": len(STORE.states), "events": len(STORE.events)}
