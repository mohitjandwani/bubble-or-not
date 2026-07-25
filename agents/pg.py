"""Postgres store — same surface as MemoryStore, backed by the schema.sql tables.
Rules from agents-README §6: small pool (free tiers cap connections), one short
transaction per write, rows commit as each probe lands (the DB IS the event log).
"""
from __future__ import annotations

import json
from typing import Optional

import asyncpg

from schema import Evidence, RunEvent, StatePayload


class PGStore:
    def __init__(self) -> None:
        self.pool: asyncpg.Pool | None = None

    async def init(self, dsn: str) -> None:
        self.pool = await asyncpg.create_pool(dsn, min_size=2, max_size=8)
        # fresh database (e.g. first boot on Render) → apply the DDL once
        async with self.pool.acquire() as con:
            exists = await con.fetchval(
                "SELECT to_regclass('public.runs') IS NOT NULL")
            if not exists:
                from pathlib import Path
                ddl = (Path(__file__).resolve().parents[1] / "schema.sql").read_text()
                await con.execute(ddl)

    # ---- writes -------------------------------------------------------------
    async def put_state(self, state: StatePayload, *, make_current: bool = True) -> None:
        # runs row is the replay unit: full payload as JSONB + queryable columns
        async with self.pool.acquire() as con:
            await con.execute(
                """INSERT INTO runs(run_id, status, bti, prev_bti, total_cost, config_version, state_json,
                                    finished_at)
                   VALUES($1,$2,$3,$4,$5,$6,$7, CASE WHEN $2='done' THEN now() END)
                   ON CONFLICT(run_id) DO UPDATE SET
                     status=$2, bti=$3, prev_bti=$4, total_cost=$5, state_json=$7,
                     finished_at=CASE WHEN $2='done' THEN now() ELSE runs.finished_at END""",
                state.run_id, state.status, state.bti, state.prev_bti,
                state.total_cost, state.config_version, state.model_dump_json())
            for fr in state.factors:
                await con.execute(
                    """INSERT INTO factor_results(run_id, factor, sub_metrics, score, state, cost, as_of)
                       VALUES($1,$2,$3,$4,$5,$6,$7)
                       ON CONFLICT(run_id, factor) DO UPDATE SET
                         sub_metrics=$3, score=$4, state=$5, cost=$6, as_of=$7""",
                    state.run_id, fr.factor, json.dumps(fr.sub_metrics), fr.score,
                    fr.state, fr.cost, fr.as_of)
            for sig in state.signatures:
                await con.execute(
                    """INSERT INTO signatures(run_id, signature_id, lamp, strong_count, weak_count,
                                              driving_evidence_ids)
                       VALUES($1,$2,$3,$4,$5,$6)
                       ON CONFLICT(run_id, signature_id) DO UPDATE SET
                         lamp=$3, strong_count=$4, weak_count=$5, driving_evidence_ids=$6""",
                    state.run_id, sig.signature_id, sig.lamp, sig.strong_count,
                    sig.weak_count, sig.driving_evidence_ids)

    async def put_evidence(self, run_id: str, rows: list[Evidence]) -> None:
        async with self.pool.acquire() as con:
            for r in rows:
                await con.execute(
                    """INSERT INTO evidence(evidence_id, run_id, factor, probe_id, "window",
                                            metric, value, unit, as_of, quote, source_url,
                                            confidence, provenance)
                       VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                       ON CONFLICT(evidence_id) DO NOTHING""",
                    r.evidence_id, run_id, r.factor, r.probe_id, r.window, r.metric,
                    r.value, r.unit, r.as_of, r.quote, r.source_url, r.confidence,
                    json.dumps(r.provenance))

    async def emit(self, event: RunEvent) -> RunEvent:
        async with self.pool.acquire() as con:
            row = await con.fetchrow(
                """INSERT INTO run_events(run_id, ts, factor, probe_id, event_type, endpoint,
                                          params_summary, cost, elapsed_ms, cache_hit, detail)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING id""",
                event.run_id, event.ts, event.factor, event.probe_id, event.event_type,
                event.endpoint, event.params_summary, event.cost, event.elapsed_ms,
                event.cache_hit, json.dumps(event.detail))
            event.id = row["id"]
            return event

    # ---- reads --------------------------------------------------------------
    async def state(self, run_id: Optional[str] = None) -> Optional[StatePayload]:
        async with self.pool.acquire() as con:
            if run_id:
                row = await con.fetchrow("SELECT state_json FROM runs WHERE run_id=$1", run_id)
            else:
                row = await con.fetchrow(
                    "SELECT state_json FROM runs ORDER BY started_at DESC LIMIT 1")
        return StatePayload.model_validate_json(row["state_json"]) if row else None

    async def events_since(self, since: int, limit: int = 200) -> list[RunEvent]:
        async with self.pool.acquire() as con:
            rows = await con.fetch(
                "SELECT * FROM run_events WHERE id > $1 ORDER BY id LIMIT $2", since, limit)
        return [RunEvent(
            id=r["id"], run_id=r["run_id"], ts=r["ts"], event_type=r["event_type"],
            factor=r["factor"], probe_id=r["probe_id"], endpoint=r["endpoint"],
            params_summary=r["params_summary"],
            cost=float(r["cost"]) if r["cost"] is not None else None,
            elapsed_ms=r["elapsed_ms"], cache_hit=r["cache_hit"],
            detail=json.loads(r["detail"]) if r["detail"] else {}) for r in rows]

    async def evidence_for(self, factor: str, run_id: Optional[str] = None) -> list[Evidence]:
        async with self.pool.acquire() as con:
            if run_id is None:
                row = await con.fetchrow("SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1")
                if row is None:
                    return []
                run_id = row["run_id"]
            rows = await con.fetch(
                'SELECT * FROM evidence WHERE run_id=$1 AND factor=$2', run_id, factor)
        return [Evidence(
            evidence_id=r["evidence_id"], run_id=r["run_id"], factor=r["factor"],
            probe_id=r["probe_id"], window=r["window"], metric=r["metric"],
            value=float(r["value"]) if r["value"] is not None else None,
            unit=r["unit"], as_of=r["as_of"], quote=r["quote"], source_url=r["source_url"],
            confidence=r["confidence"],
            provenance=json.loads(r["provenance"]) if r["provenance"] else {}) for r in rows]

    async def has_runs(self) -> bool:
        async with self.pool.acquire() as con:
            return bool(await con.fetchval("SELECT count(*) FROM runs"))

    async def cache_get(self, probe_id: str, window: str, ttl_hours: float):
        async with self.pool.acquire() as con:
            row = await con.fetchrow(
                '''SELECT payload FROM probe_cache
                   WHERE probe_id=$1 AND "window"=$2
                     AND fetched_at > now() - ($3 || ' hours')::interval''',
                probe_id, window, str(ttl_hours))
        return json.loads(row["payload"]) if row else None

    async def cache_put(self, probe_id: str, window: str, payload: dict) -> None:
        async with self.pool.acquire() as con:
            await con.execute(
                '''INSERT INTO probe_cache(probe_id, "window", payload)
                   VALUES($1,$2,$3)
                   ON CONFLICT(probe_id, "window") DO UPDATE SET
                     payload=$3, fetched_at=now()''',
                probe_id, window, json.dumps(payload))
