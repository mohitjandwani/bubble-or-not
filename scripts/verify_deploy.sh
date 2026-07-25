#!/usr/bin/env bash
# Pass 6 acceptance checks against a live Render deploy.
#
#   ./scripts/verify_deploy.sh <web-url> [api-url]
#   ./scripts/verify_deploy.sh https://bubble-web.onrender.com --with-rescore
#
# Read-only by default. --with-rescore additionally triggers a real run, which
# spends You.com budget ($0.60-2.20 with Pass 3+ probes live) — opt in on purpose.
#
# Needs ADMIN_KEY in the environment for the auth checks (sourced from .env if present).

set -uo pipefail

WEB="${1:-}"
API="${2:-https://bubble-api.onrender.com}"
[[ "$API" == --* ]] && API="https://bubble-api.onrender.com"
WITH_RESCORE=0
for a in "$@"; do [[ "$a" == "--with-rescore" ]] && WITH_RESCORE=1; done

if [[ -z "$WEB" ]]; then
  echo "usage: $0 <web-url> [api-url] [--with-rescore]" >&2
  exit 2
fi

WEB="${WEB%/}"; API="${API%/}"
[[ -f .env ]] && set -a && . ./.env 2>/dev/null && set +a

pass=0; fail=0
ok(){ printf '  \033[32mPASS\033[0m  %s\n' "$1"; pass=$((pass+1)); }
no(){ printf '  \033[31mFAIL\033[0m  %s\n' "$1"; [[ -n "${2:-}" ]] && printf '        %s\n' "$2"; fail=$((fail+1)); }

echo "web: $WEB"
echo "api: $API"

# ---- API directly ---------------------------------------------------------
echo
echo "[api]"
health=$(curl -sS -m 25 "$API/healthz" 2>&1)
if [[ "$health" == *'"ok":true'* ]]; then ok "/healthz reachable"; else no "/healthz reachable" "$health"; fi
if [[ "$health" == *'PGStore'* ]]; then
  ok "backed by Postgres (PGStore)"
elif [[ "$health" == *'MemoryStore'* ]]; then
  no "backed by Postgres" "got MemoryStore — DATABASE_URL never reached the app; runs will not survive a restart"
else
  no "backed by Postgres" "could not read store from: $health"
fi

code=$(curl -sS -o /dev/null -w '%{http_code}' -m 25 "$API/state")
[[ "$code" == 200 ]] && ok "GET /state -> 200" || no "GET /state -> 200" "got $code"

run_id=$(curl -sS -m 25 "$API/state" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("run_id",""))' 2>/dev/null)
[[ -n "$run_id" ]] && ok "state has a run_id ($run_id)" || no "state has a run_id"

if [[ -n "$run_id" ]]; then
  code=$(curl -sS -o /dev/null -w '%{http_code}' -m 25 "$API/state?run_id=$run_id")
  [[ "$code" == 200 ]] && ok "replay: /state?run_id=$run_id -> 200" || no "replay -> 200" "got $code"
fi

code=$(curl -sS -o /dev/null -w '%{http_code}' -m 25 "$API/state?run_id=run-does-not-exist")
[[ "$code" == 404 ]] && ok "unknown run_id -> 404" || no "unknown run_id -> 404" "got $code"

# ---- admin auth (no run triggered: bad keys are rejected before any work) --
echo
echo "[auth]"
code=$(curl -sS -o /dev/null -w '%{http_code}' -m 25 -X POST "$API/rescore")
[[ "$code" == 401 ]] && ok "POST /rescore with no key -> 401" || no "no key -> 401" "got $code"

code=$(curl -sS -o /dev/null -w '%{http_code}' -m 25 -X POST -H 'X-Admin-Key: wrong' "$API/rescore")
[[ "$code" == 401 ]] && ok "POST /rescore with wrong key -> 401" || no "wrong key -> 401" "got $code"

# ---- SPA + rewrites -------------------------------------------------------
echo
echo "[spa]"
root=$(curl -sS -m 25 -o /dev/null -w '%{http_code} %{content_type}' "$WEB/")
[[ "$root" == 200* ]] && ok "static root -> 200 ($root)" || no "static root -> 200" "got $root"

# The whole point of the rewrites: /state must resolve THROUGH the static origin.
proxied=$(curl -sS -m 25 "$WEB/state" 2>&1)
if [[ "$proxied" == *'"run_id"'* ]]; then
  ok "rewrite works: $WEB/state proxies to the API"
else
  no "rewrite works: $WEB/state proxies to the API" \
     "got: $(printf '%.160s' "$proxied") — if this is HTML, the SPA catch-all is swallowing /state, or the destination hostname is wrong (DEPLOY.md step 4)"
fi

ev=$(curl -sS -m 25 -o /dev/null -w '%{http_code}' "$WEB/evidence/f5")
[[ "$ev" == 200 ]] && ok "rewrite works: /evidence/f5 -> 200" || no "/evidence/f5 -> 200" "got $ev"

# /fixtures must NOT be rewritten — it is the offline fallback.
fx=$(curl -sS -m 25 "$WEB/fixtures/state.json" 2>&1)
[[ "$fx" == *'"run_id"'* ]] && ok "/fixtures/state.json still served locally (offline fallback intact)" \
  || no "/fixtures/state.json served locally" "$(printf '%.120s' "$fx")"

# ---- optional: real run + 409 concurrency ---------------------------------
if [[ "$WITH_RESCORE" == 1 ]]; then
  echo
  echo "[rescore]  (spending real budget)"
  if [[ -z "${ADMIN_KEY:-}" ]]; then
    no "ADMIN_KEY available" "set it in .env or the environment"
  else
    c1=$(curl -sS -o /dev/null -w '%{http_code}' -m 30 -X POST -H "X-Admin-Key: $ADMIN_KEY" "$API/rescore")
    [[ "$c1" == 202 ]] && ok "first rescore -> 202" || no "first rescore -> 202" "got $c1"
    c2=$(curl -sS -o /dev/null -w '%{http_code}' -m 30 -X POST -H "X-Admin-Key: $ADMIN_KEY" "$API/rescore")
    [[ "$c2" == 409 ]] && ok "second rescore during run -> 409" || no "concurrent rescore -> 409" "got $c2"
    st=$(curl -sS -m 25 "$API/state" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("status",""))' 2>/dev/null)
    [[ "$st" == running ]] && ok "state flipped to running" || no "state flipped to running" "got '$st'"
  fi
else
  echo
  echo "[rescore]  skipped — pass --with-rescore to test it (costs You.com budget)"
fi

echo
echo "=================================================="
echo "$pass passed, $fail failed"
[[ "$fail" == 0 ]] || exit 1
