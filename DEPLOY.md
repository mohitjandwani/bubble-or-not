# Deploy — one-time setup, then push to main

## 🟢 Live now

| | |
|---|---|
| **Public dashboard** | <https://bubble-web-ym57.onrender.com> |
| API | <https://bubble-api-y4s4.onrender.com> |
| Repo | <https://github.com/mohitjandwani/bubble-or-not> (private) |

**Deploying is now just:** `git push origin main`. Both services rebuild automatically
(`autoDeploy: yes`, branch `main`).

Render appended random suffixes (`-y4s4`, `-ym57`) because the bare names were taken. The rewrites in
`render.yaml` have been reconciled to the real API hostname — if you ever recreate the services, redo
that reconciliation or every API call from the SPA will 404.

### Resource IDs

| Resource | ID | Plan |
|---|---|---|
| `bubble-api` | `srv-d9i0pp7abvsc73a80odg` | free |
| `bubble-web` | `srv-d9i0pub7uimc73aruieg` | free (static) |
| `bubble-db` | `dpg-d9i0phv15fvs73dl21r0-a` | free Postgres 16 |

### Free-tier caveats you are now living with

- **Spin-down:** the API sleeps after ~15 min idle; the next request takes ~50s. PLAN.md §10 calls this
  out and Pass 6 tests against it. **Warm the URL right before any demo**, or upgrade to Starter.
- **The database expires.** Render deletes free Postgres after 30 days. Before then, either upgrade it or
  re-apply `schema.sql` to a new one.
- The services were created directly through the Render REST API, not by applying `render.yaml`. The
  blueprint is accurate and validates (`"valid": true`), but it is documentation until someone applies it —
  so edits to `render.yaml` alone will **not** change the running services.

---

## ⛔ The one rule

**Never automate `schema.sql`.** Line 3 is `DROP TABLE IF EXISTS ... CASCADE`. Putting it in
`buildCommand`, `preDeployCommand`, or app startup wipes every stored run on *every deploy* — including the
past `run_id` that PLAN.md Pass 8 relies on as demo insurance (`GET /state?run_id=...`). You would
discover this on stage.

Apply it **once, by hand**, in step 5 below. Then never again.

---

## Prerequisites

Running `render blueprints validate ./render.yaml` today returns two expected errors. Both are account
state, not blueprint bugs — the YAML itself is confirmed valid.

**1. `need_payment_info`** (on `databases[0]` and `services[0]`)

Credits do not remove this: Render requires a payment method on file before provisioning any paid
resource.

> Render Dashboard → **Billing** → add a payment method, and confirm your credits are applied to
> workspace *Mohit Jandwani's Workspace* (`tea-cspvlbogph6c73ftadg0`).

**2. `branch main could not be found`**

`main` *does* exist on GitHub — Render simply cannot see it yet, because its GitHub App has not been
granted access to a private repo. This clears itself during step 2 when you connect the repo. Do not
chase it before then.

> If it persists after step 2: GitHub → **Settings → Applications → Render** → grant access to
> `bubble-or-not`.

Both cleared when this prints `"valid": true`:

```bash
render blueprints validate ./render.yaml
```

Starter is not optional — PLAN.md §10 flags free-tier spin-down as a demo-day gotcha, and Pass 6's own
checklist tests *"wait 20+ min idle, reload → instant"*. Only a paid instance passes.

---

## One-time setup

### 1. Validate the blueprint

```bash
render blueprints validate ./render.yaml
```

Free and instant. Expect the two Prerequisite errors until billing is set up and Render can see the repo;
anything *else* should be fixed before spending a deploy.

### 2. Create the Blueprint  ⚠️ Dashboard only

The Render CLI **cannot create services** — v2.22.0 exposes only `blueprints validate` and
`services list`. This step is irreducibly manual.

Render Dashboard → **New → Blueprint** → select `mohitjandwani/bubble-or-not` → Apply.

It reads `render.yaml` and provisions `bubble-db`, `bubble-api`, and `bubble-web`.

### 3. Set the four secrets  ⚠️ Dashboard only

Marked `sync: false` in the blueprint, so Render prompts for them and never stores them in git. Copy the
values from your local `.env`:

| Key | Where it's used |
|---|---|
| `YOU_API_KEY` | You.com Research/Search — every F1–F6 probe |
| `ANTHROPIC_API_KEY` | Haiku fallback in the `extract()` chain |
| `FMP_API_KEY` | F5 index constituents, fed funds |
| `ADMIN_KEY` | Gates `POST /rescore` |

`DATABASE_URL` is wired automatically from `bubble-db` — do not set it by hand.

### 4. Wait for the first build, then confirm the API URL

```bash
render services list
```

Render usually assigns `bubble-api.onrender.com`, but **if that hostname was taken it appends a suffix**.
The rewrites in `render.yaml` hardcode `https://bubble-api.onrender.com`. If your actual URL differs,
update all four `destination:` lines and push — otherwise the SPA's API calls 404.

### 5. Apply the schema — once  🔴 destructive

```bash
render psql bubble-db < schema.sql
```

Then **never run this again**. See "The one rule" above.

### 6. Verify the API before touching the SPA

```bash
curl -s https://bubble-api.onrender.com/healthz
# expect: {"ok":true,"store":"PGStore"}
```

`"store":"MemoryStore"` means `DATABASE_URL` never reached the app. Stop and fix that — every run you do
afterwards evaporates on restart.

### 7. Seed one real run

```bash
curl -X POST https://bubble-api.onrender.com/rescore \
  -H "X-Admin-Key: $ADMIN_KEY"
```

Gives the page real data, and gives you a `run_id` to bookmark as the Pass 8 replay URL:

```bash
curl -s https://bubble-api.onrender.com/state | python3 -c 'import json,sys;print(json.load(sys.stdin)["run_id"])'
```

### 8. Run the acceptance check

```bash
./scripts/verify_deploy.sh https://bubble-web.onrender.com
```

---

## Every deploy after that

```bash
git push origin main
```

Both services rebuild on push (`autoDeploy: true`, `branch: main`). Nothing else to do.

- **Config-only changes** still get their own commit — PLAN.md's Forge audit story depends on
  `runs.config_version` tracking `/config` separately.
- Watch a deploy: `render logs bubble-api --tail`
- Roll back: Render Dashboard → service → **Deploys** → pick a previous deploy → **Redeploy**.
  Rolling back code does **not** roll back the database.

---

## Pass 6 acceptance checklist

From PLAN.md. `scripts/verify_deploy.sh` automates rows 2–3.

| Check | How | Pass condition |
|---|---|---|
| Public URL loads on your phone | Open the static URL, watch devtools | `/state` every 15s idle, 2s while running |
| `curl` rescore → live run on the public page | Step 7 above | Page flips to `running` within 2s |
| Bad admin key → 401; two rescores → 409 | `verify_deploy.sh` | 401 then 409 |
| 20+ min idle, reload → instant | Leave it, come back, hard reload | Fast first byte. **Fails on free tier by design.** |
| Cron fires | See below | A `run.started` event with no human involved |

---

## Enabling the scheduled rescore (later)

Left out of the initial deploy on purpose: Pass 3+ probes are live, so every run spends real You.com
budget ($0.60–2.20 per full run).

To enable: uncomment the `bubble-cron` block at the bottom of `render.yaml`, set `ADMIN_KEY` on it in the
Dashboard, and `git push origin main`. The Blueprint sync creates it.

To test it without waiting 6 hours, temporarily set `schedule: "*/10 * * * *"`, confirm via
`render logs bubble-cron`, then restore `"0 */6 * * *"`.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Build green, service crashes on boot | A dependency is imported but not in `requirements.txt` | Check `render logs bubble-api` for `ModuleNotFoundError`. This is why `asyncpg` was added. |
| `/healthz` says `MemoryStore` | `DATABASE_URL` not injected | Confirm the `fromDatabase` block and that `bubble-db` finished provisioning |
| SPA loads but every number is blank | Rewrite destinations point at the wrong hostname | Step 4 — reconcile `render.yaml` with `render services list` |
| `relation "runs" does not exist` | Schema never applied | Step 5, once |
| All runs vanished after a deploy | Something is running `schema.sql` automatically | Remove it. See "The one rule". |
| First request after idle takes ~50s | Service is on the free tier | Upgrade `bubble-api` to Starter |
| Boot OOM | Starter is 512MB; `yfinance` pulls pandas + numpy | Upgrade the instance, or trim the dependency |
| `need_payment_info` | No payment method on the workspace | Use `plan: free` everywhere (what we did), or add a card |
| First deploy dies with `UndefinedTableError: relation "runs" does not exist` | The service booted before `schema.sql` was applied — `api.py` startup queries `runs` | Apply the schema, then redeploy. Harmless ordering artifact, not a code bug. |
| `psql: SSL connection has been closed unexpectedly` against Render Postgres | **Local psql 17/18 defaults to direct TLS negotiation, which Render's proxy rejects.** Not a Render or credentials problem. | Use asyncpg instead — it connects fine: `asyncpg.connect(dsn, ssl='require')`. This is how the schema was applied. |
| Any external DB connection hangs then closes | Render Postgres ships with an **empty IP allowlist**, blocking all external access | Add your IP: `PATCH /v1/postgres/{id}` with `ipAllowList: [{"cidrBlock":"<your-ip>/32"}]`. Internal access from `bubble-api` is unaffected. |
