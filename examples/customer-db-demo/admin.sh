#!/usr/bin/env bash
# admin.sh — the operator's control plane (local stand-in).
#
# In production this is the Threshold control plane UI/API; here it's a thin wrapper over
# the policy file so a demo can show admin control live. Each command changes one policy
# value and re-applies it (full restart, because the rule-runner caches compiled rules).
#
#   ./admin.sh show                     # current policy
#   ./admin.sh allow 131-246            # row scope: ids/ranges, e.g. 42  131-246  42,131-246
#   ./admin.sh allow-host partner       # add a host to the egress allowlist
#   ./admin.sh deny-host partner        # remove a host from the egress allowlist
#   ./admin.sh writes on|off            # enable/disable DB writes (read-only switch)
#   ./admin.sh reset                    # restore demo defaults
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] || cp .env.example .env
PORT="$(grep -E '^T8_PORT=' .env | cut -d= -f2 || echo 18020)"

_get() { grep -E "^$1=" .env | head -1 | cut -d= -f2- || true; }
_set() {
  if grep -qE "^$1=" .env; then sed -i.bak "s|^$1=.*|$1=$2|" .env && rm -f .env.bak
  else printf '%s=%s\n' "$1" "$2" >> .env; fi
}
_apply() {
  echo "▸ applying policy (recreating t8engine + rule-runner so they reload)…"
  # Re-export the freshly-edited .env into this shell, so docker compose's variable
  # interpolation sees the NEW values. (Without this, when admin.sh runs inside the
  # demo-runner container, the runner's boot-time env_file values would still be in
  # the shell and would override the updated .env file.)
  set -a; . ./.env; set +a
  # Both t8engine AND rule-runner must be recreated. Empirically (v0.1) the new SPEC
  # only takes effect once rule-runner is replaced too — recreating just t8engine
  # leaves the previous compiled rule live. --no-deps keeps mock-db / partner /
  # attacker / demo-runner up (the runner must not be torn down when admin.sh is
  # invoked from inside it).
  docker compose up -d --force-recreate --no-deps t8engine rule-runner >/dev/null 2>&1
  health="${T8_HEALTHCHECK:-http://localhost:${PORT}/healthz}"
  for i in $(seq 1 30); do curl -fsS "$health" >/dev/null 2>&1 && break || sleep 1; done
  echo "▸ live."
}

case "${1:-show}" in
  show)
    echo "Current policy (admin-controlled):"
    echo "  rows allowed      : $(_get ALLOWED_CUSTOMER_RANGE)"
    echo "  egress allowlist  : $(_get ALLOWED_HOSTS)"
    echo "  db writes allowed : $(_get DB_WRITES_ALLOWED)"
    ;;
  allow)
    _set ALLOWED_CUSTOMER_RANGE "${2:?usage: ./admin.sh allow <spec>  e.g. 131-246}"
    echo "▸ admin: authorized row scope → '${2}'"; _apply ;;
  allow-host)
    h="${2:?usage: ./admin.sh allow-host <host>}"; cur="$(_get ALLOWED_HOSTS)"
    case ",$cur," in *",$h,"*) echo "'$h' already on the allowlist";; *) _set ALLOWED_HOSTS "${cur:+$cur,}$h";; esac
    echo "▸ admin: egress allowlist → $(_get ALLOWED_HOSTS)"; _apply ;;
  deny-host)
    h="${2:?usage: ./admin.sh deny-host <host>}"; cur="$(_get ALLOWED_HOSTS)"
    new="$(echo "$cur" | tr ',' '\n' | grep -vx "$h" | paste -sd, -)"
    _set ALLOWED_HOSTS "$new"; echo "▸ admin: egress allowlist → $new"; _apply ;;
  writes)
    case "${2:?usage: ./admin.sh writes <on|off>}" in
      on)  _set DB_WRITES_ALLOWED true ;;
      off) _set DB_WRITES_ALLOWED false ;;
      *)   echo "usage: ./admin.sh writes <on|off>"; exit 1 ;;
    esac
    echo "▸ admin: db writes allowed → $(_get DB_WRITES_ALLOWED)"; _apply ;;
  reset)
    _set ALLOWED_CUSTOMER_RANGE 42
    _set ALLOWED_HOSTS "mock-db,api.anthropic.com"
    _set DB_WRITES_ALLOWED false
    echo "▸ admin: policy reset to demo defaults"; _apply ;;
  *)
    echo "usage: ./admin.sh [show | allow <spec> | allow-host <h> | deny-host <h> | writes <on|off> | reset]"
    exit 1 ;;
esac
