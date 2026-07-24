"""In-memory store — Pass 1 stand-in for Postgres. Same read/write surface the
Pass 2 asyncpg store will expose, so the API layer doesn't change when we swap."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from schema import Evidence, RunEvent, StatePayload

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"


class MemoryStore:
    def __init__(self) -> None:
        self.states: dict[str, StatePayload] = {}   # run_id -> full snapshot
        self.evidence: dict[str, list[Evidence]] = {}  # run_id -> rows
        self.events: list[RunEvent] = []            # global log, id = monotonic cursor
        self.current_run_id: Optional[str] = None
        self._next_event_id = 1

    # ---- seeding -----------------------------------------------------------
    def load_fixtures(self) -> None:
        state = StatePayload.model_validate_json((FIXTURES / "state.json").read_text())
        rows = [Evidence.model_validate(r) for r in json.loads((FIXTURES / "evidence.json").read_text())]
        self.states[state.run_id] = state
        self.evidence[state.run_id] = rows
        self.current_run_id = state.run_id

    # ---- writes (the fake pipeline calls these; real one will too) ---------
    def put_state(self, state: StatePayload, *, make_current: bool = True) -> None:
        self.states[state.run_id] = state
        if make_current:
            self.current_run_id = state.run_id

    def put_evidence(self, run_id: str, rows: list[Evidence]) -> None:
        self.evidence.setdefault(run_id, []).extend(rows)

    def emit(self, event: RunEvent) -> RunEvent:
        event.id = self._next_event_id
        self._next_event_id += 1
        self.events.append(event)
        return event

    # ---- reads (the API layer calls these) ---------------------------------
    def state(self, run_id: Optional[str] = None) -> Optional[StatePayload]:
        return self.states.get(run_id or self.current_run_id or "")

    def events_since(self, since: int, limit: int = 200) -> list[RunEvent]:
        return [e for e in self.events if e.id > since][:limit]

    def evidence_for(self, factor: str, run_id: Optional[str] = None) -> list[Evidence]:
        rows = self.evidence.get(run_id or self.current_run_id or "", [])
        return [r for r in rows if r.factor == factor]


STORE = MemoryStore()
