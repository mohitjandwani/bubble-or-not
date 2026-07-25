# Deploy — one-time setup, then push to main

**After setup, deploying is:** `git push origin main`. Render rebuilds both services automatically.

Repo: <https://github.com/mohitjandwani/bubble-or-not> (private)
Blueprint: [`render.yaml`](./render.yaml) — 3 resources (Postgres, API, static SPA)

---

## ⛔ The one rule

**Never automate `schema.sql`.** Line 3 is `DROP TABLE IF EXISTS ... CASCADE`. Putting it in
`buildCommand`, `preDeployCommand`, or app startup wipes every stored run on *every deploy* — including the
past `run_id` that PLAN.md Pass 8 relies on as demo insurance (`GET /state?run_id=...`). You would
discover this on stage.

Apply it **once, by hand**, in step 5 below. Then never again.

---

## Prerequisite — payment info

`render blueprints validate` currently returns `need_payment_info` for the Postgres database and the
Starter web service. Credits do not remove this: Render requires a payment method on file before it
will provision any paid resource.

> **Do this first:** Render Dashboard → **Billing** → add a payment method, and confirm your credits are
> applied to workspace *Mohit Jandwani's Workspace* (`tea-cspvlbogph6c73ftadg0`).

Nothing below works until that check passes:

```bash
render blueprints validate ./render.yaml   # must print "valid": true
```

Starter is not optional — PLAN.md §10 flags free-tier spin-down as a demo-day gotcha, and Pass 6's own
checklist tests *"wait 20+ min idle, reload → instant"*. Only a paid instance passes.

---

## One-time setup

### 1. Validate the blueprint

```bash
render blueprints validate ./render.yaml
```

Fix any error before spending a deploy. This is free and instant.

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
| `need_payment_info` | No payment method on the workspace | See Prerequisite |
