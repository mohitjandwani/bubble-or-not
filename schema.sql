-- Bubble or Not — Postgres DDL (agents-README.md §6, verbatim + config_version).
-- Recreatable in one command:  psql "$DATABASE_URL" -f schema.sql
DROP TABLE IF EXISTS probe_cache, registry_edges, signatures, factor_results,
                     evidence, run_events, runs CASCADE;

CREATE TABLE runs(
  run_id        TEXT PRIMARY KEY,
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at   TIMESTAMPTZ,
  status        TEXT NOT NULL,              -- running | done | failed
  total_cost    NUMERIC(10,4) DEFAULT 0,
  bti           NUMERIC(5,2),
  prev_bti      NUMERIC(5,2),
  config_version TEXT DEFAULT 'dev',
  state_json    JSONB                        -- full StatePayload snapshot (replay = one read)
);

CREATE TABLE run_events(
  id             BIGSERIAL PRIMARY KEY,     -- monotonic cursor for GET /events?since=
  run_id         TEXT REFERENCES runs(run_id) ON DELETE CASCADE,
  ts             TIMESTAMPTZ NOT NULL DEFAULT now(),
  factor         TEXT, probe_id TEXT, event_type TEXT,
  endpoint       TEXT, params_summary TEXT,
  cost           NUMERIC(10,4), elapsed_ms INTEGER,
  cache_hit      BOOLEAN DEFAULT false,
  detail         JSONB
);
CREATE INDEX ON run_events(run_id, id);

CREATE TABLE evidence(
  evidence_id  TEXT PRIMARY KEY,
  run_id       TEXT REFERENCES runs(run_id) ON DELETE CASCADE,
  factor       TEXT NOT NULL, probe_id TEXT, "window" TEXT,
  metric       TEXT NOT NULL, value NUMERIC, unit TEXT, as_of DATE,
  quote        TEXT, source_url TEXT,
  confidence   TEXT CHECK (confidence IN ('high','medium','low')),
  provenance   JSONB
);
CREATE INDEX ON evidence(run_id, factor);
CREATE INDEX ON evidence USING GIN (provenance);

CREATE TABLE factor_results(
  run_id      TEXT REFERENCES runs(run_id) ON DELETE CASCADE,
  factor      TEXT, sub_metrics JSONB, score NUMERIC(5,2),
  state       TEXT CHECK (state IN ('ok','stale','low_coverage','failed')),
  cost        NUMERIC(10,4),
  as_of       TIMESTAMPTZ,
  PRIMARY KEY(run_id, factor)
);

CREATE TABLE signatures(
  run_id       TEXT REFERENCES runs(run_id) ON DELETE CASCADE,
  signature_id TEXT, lamp TEXT CHECK (lamp IN ('fired','partial','watch','not','no_data')),
  strong_count INTEGER DEFAULT 0, weak_count INTEGER DEFAULT 0,
  driving_evidence_ids TEXT[],
  PRIMARY KEY(run_id, signature_id)
);

CREATE TABLE registry_edges(
  edge_id      TEXT PRIMARY KEY,
  from_entity  TEXT, to_entity TEXT, archetype TEXT,
  amount_usd_m NUMERIC, announced_date DATE,
  status       TEXT CHECK (status IN ('verified','announced_only','contradicted','unverified')),
  seed_source_url TEXT, last_verified_run TEXT,
  UNIQUE(from_entity, to_entity, archetype)   -- dedup guard for scanner upserts
);

CREATE TABLE probe_cache(
  probe_id   TEXT, "window" TEXT,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  payload    JSONB,
  PRIMARY KEY(probe_id, "window")
);
