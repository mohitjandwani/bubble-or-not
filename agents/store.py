"""Store holder + in-memory implementation (async surface identical to PGStore).

`agents.store.STORE` is late-bound: api.py swaps in a PGStore at startup when
DATABASE_URL is set. Everything else reads it through this module, never a
direct import of the object, so the swap is invisible to callers.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from schema import Evidence, RunEvent, StatePayload

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"


class MemoryStore:
    def __init__(self) -> None:
        self.states: dict[str, StatePayload] = {}
        self.evidence: dict[str, list[Evidence]] = {}
        self.events: list[RunEvent] = []
        self.current_run_id: Optional[str] = None
        self._next_event_id = 1

    async def put_state(self, state: StatePayload, *, make_current: bool = True) -> None:
        self.states[state.run_id] = state
        if make_current:
            self.current_run_id = state.run_id

    async def put_evidence(self, run_id: str, rows: list[Evidence]) -> None:
        self.evidence.setdefault(run_id, []).extend(rows)

    async def emit(self, event: RunEvent) -> RunEvent:
        event.id = self._next_event_id
        self._next_event_id += 1
        self.events.append(event)
        return event

    async def state(self, run_id: Optional[str] = None) -> Optional[StatePayload]:
        return self.states.get(run_id or self.current_run_id or "")

    async def events_since(self, since: int, limit: int = 200) -> list[RunEvent]:
        return [e for e in self.events if e.id > since][:limit]

    async def evidence_for(self, factor: str, run_id: Optional[str] = None) -> list[Evidence]:
        rows = self.evidence.get(run_id or self.current_run_id or "", [])
        return [r for r in rows if r.factor == factor]

    async def has_runs(self) -> bool:
        return bool(self.states)

    async def cache_get(self, probe_id: str, window: str, ttl_hours: float):
        hit = getattr(self, "_cache", {}).get((probe_id, window))
        if not hit:
            return None
        fetched_at, payload = hit
        from datetime import datetime, timezone
        age_h = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
        return payload if age_h <= ttl_hours else None

    async def cache_put(self, probe_id: str, window: str, payload: dict) -> None:
        from datetime import datetime, timezone
        if not hasattr(self, "_cache"):
            self._cache = {}
        self._cache[(probe_id, window)] = (datetime.now(timezone.utc), payload)


STORE = MemoryStore()  # api.py may replace with PGStore at startup


def set_store(impl) -> None:
    global STORE
    STORE = impl


def load_fixture_payload() -> tuple[StatePayload, list[Evidence]]:
    state = StatePayload.model_validate_json((FIXTURES / "state.json").read_text())
    rows = [Evidence.model_validate(r) for r in json.loads((FIXTURES / "evidence.json").read_text())]
    return state, rows
