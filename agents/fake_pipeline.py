"""Pass 1 fake pipeline. Emits the FULL run_events vocabulary over ~15s and
perturbs scores/lamps so the SPA's poll-diff choreography is exercisable long
before any real agent exists. Replaced factor-by-factor in Passes 2-5.

Deterministic-ish: perturbations are seeded by run number, so rescore N always
produces the same numbers (useful when testing the UI diff by hand).
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone

from schema import RunEvent, StatePayload, compute_bti, stage_sentence
from agents.store import STORE

FACTORS = ["f1", "f2", "f3", "f4", "f5", "f6"]
FAKE_ENDPOINT = {"f1": "search", "f2": "finance_research", "f3": "research",
                 "f4": "finance_research", "f5": "fmp", "f6": "search"}
FAKE_COST = {"f1": 0.02, "f2": 0.11, "f3": 0.05, "f4": 0.11, "f5": 0.0, "f6": 0.01}

_run_counter = 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _emit(run_id: str, event_type: str, **kw) -> None:
    STORE.emit(RunEvent(id=0, run_id=run_id, ts=_now(), event_type=event_type, **kw))


def _relamp(sig) -> None:
    """Deterministic lamp rule (HANDOVER §4). no_data rows never change."""
    if sig.lamp == "no_data":
        return
    if sig.strong_count >= 1:
        sig.lamp = "fired"
    elif sig.weak_count >= sig.k_weak:
        sig.lamp = "partial"
    elif sig.weak_count >= 1:
        sig.lamp = "watch"
    else:
        sig.lamp = "not"


async def run_fake_pipeline() -> str:
    global _run_counter
    _run_counter += 1
    rng = random.Random(_run_counter)  # same run number -> same perturbation

    prev = STORE.state()
    assert prev is not None, "store must be seeded before rescoring"
    run_id = f"run-{_run_counter:04d}"

    state = prev.model_copy(deep=True)
    state.run_id = run_id
    state.status = "running"
    state.prev_bti = prev.bti
    state.updated_at = _now()
    STORE.put_state(state)  # visible immediately: SPA flips to 2s polling

    _emit(run_id, "run.started", detail={"factors": FACTORS})
    total_cost = 0.0

    async def run_factor(f: str) -> None:
        # Paced so a full fake run lasts ~20-25s: long enough that the SPA's 15s
        # idle poll always lands mid-run and flips to 2s cadence (real runs in
        # Pass 4 take minutes, so this is also the more honest rehearsal).
        nonlocal total_cost
        await asyncio.sleep(rng.uniform(0.5, 4.0))  # stagger starts
        _emit(run_id, "agent.started", factor=f)
        n_probes = rng.randint(2, 4)
        for i in range(n_probes):
            elapsed = rng.uniform(2.0, 5.0)
            await asyncio.sleep(elapsed)
            cost = FAKE_COST[f]
            total_cost += cost
            _emit(run_id, "agent.tool_call", factor=f, probe_id=f"{f}-probe-{i+1}",
                  endpoint=FAKE_ENDPOINT[f], params_summary="fixture window 2026-06-24to2026-07-24",
                  cost=cost, elapsed_ms=int(elapsed * 1000), cache_hit=rng.random() < 0.3)
        _emit(run_id, "agent.evidence", factor=f, detail={"count": rng.randint(1, 4)})

        fr = next(x for x in state.factors if x.factor == f)
        if fr.score is not None and fr.state != "stale":
            fr.score = round(min(100, max(0, fr.score + rng.uniform(-3, 3))), 1)
            fr.as_of = _now()
        _emit(run_id, "agent.completed", factor=f,
              detail={"score": fr.score, "state": fr.state})

    await asyncio.gather(*(run_factor(f) for f in FACTORS))

    # occasionally shift a weak-counter so a lamp visibly changes on stage
    changed: list[str] = []
    for sig in state.signatures:
        if sig.lamp in ("watch", "partial") and rng.random() < 0.4:
            sig.weak_count = max(0, sig.weak_count + rng.choice([-1, 1]))
            before = sig.lamp
            _relamp(sig)
            if sig.lamp != before:
                changed.append(sig.signature_id)

    state.bti = compute_bti({fr.factor: fr.score for fr in state.factors})
    state.stage_sentence, state.fired_count = stage_sentence(state.signatures)
    deltas = {fr.factor: (fr.score or 0) - (p.score or 0)
              for fr, p in zip(state.factors, prev.factors)}
    top = max(deltas, key=lambda k: abs(deltas[k]))
    names = {"f1": "Liquidity", "f2": "Bellwethers", "f3": "Circular financing",
             "f4": "Insiders", "f5": "Breadth", "f6": "Narrative"}
    state.driven_by = f"Driven by: {names[top]} {deltas[top]:+.1f}"
    state.total_cost = round(total_cost, 2)
    state.status = "done"
    state.updated_at = _now()

    # evidence rows for the new run = fixture rows re-stamped (real ones in Pass 3+)
    fixture_rows = STORE.evidence.get(prev.run_id) or next(iter(STORE.evidence.values()))
    STORE.put_evidence(run_id, [
        r.model_copy(update={"run_id": run_id, "evidence_id": r.evidence_id.replace(prev.run_id, run_id)})
        for r in fixture_rows
    ])
    STORE.put_state(state)
    _emit(run_id, "run.completed",
          detail={"bti": state.bti, "changed_signatures": changed, "cost": state.total_cost})
    return run_id
