# Bubble or Not

A multi-agent evidence engine that prosecutes the "is AI the new dot-com" question live, with citations.
LLMs gather evidence; scores are computed, never generated.

Specs: `hackathon_handoff/` (HANDOVER.md governs) · Build plan: `PLAN.md` · Agent internals: `agents/`

## Dev quickstart

```bash
# backend (FastAPI, port 8000) — Pass 1: in-memory store + fake pipeline
.venv/bin/uvicorn agents.api:app --reload --port 8000

# frontend (Vite, port 5173, proxies /state /events /evidence /rescore -> 8000)
cd dashboard && npm run dev

# regenerate fixtures after schema/config changes
.venv/bin/python scripts/make_fixtures.py

# trigger a rescore (admin key from .env)
curl -X POST localhost:8000/rescore -H "X-Admin-Key: $(grep ADMIN_KEY .env | cut -d= -f2)"
```

Keys live in `.env` (see `.env.example`). `.env` is loaded with `override=True` —
it always beats shell exports. Smoke tests: `scripts/smoke_you.py {balance|a|b}`,
`scripts/smoke_quant.py`.

## API (contract in `schema.py`, never changes after Pass 1)

| Endpoint | Purpose |
|---|---|
| `GET /state[?run_id]` | full dashboard payload; `run_id` = replay any past run |
| `GET /events?since=<id>` | trace rows after cursor |
| `GET /evidence/{factor}` | typed evidence + provenance for the drawer |
| `POST /rescore` | `X-Admin-Key` header; 409 if a run is active |
| `GET /healthz` | liveness |

## Demo insurance

Best replay run (rich evidence, 3-way F3 fan-out in trace, 4 fired signatures):

```
GET /state?run_id=run-0725-012147        # BTI 32.7 · 84 evidence rows
```

If a live rescore misbehaves on stage, point the SPA at this run — every run is
fully replayable because the DB is the event log. The Engine tab (`#engine`)
works regardless; its trace feed shows whatever the last runs did.
