#!/usr/bin/env bash
# Stops the backend and frontend dev processes started by `alpaca-agent-start`.
# Leaves the Docker infra (timescaledb, redis) running. Symlinked as
# `alpaca-agent-stop` in ~/bin so it can be called from any directory.
set -uo pipefail

REPO_DIR="/Users/xinzhang/projects/algoTrading/alpaca-trading-agent"
FRONTEND_PORT="$(grep -oE -- '-p [0-9]+' "$REPO_DIR/frontend/package.json" 2>/dev/null | grep -oE '[0-9]+' | head -1)"
FRONTEND_PORT="${FRONTEND_PORT:-8681}"

kill_pattern() {
  local label="$1" pattern="$2" pids
  pids="$(pgrep -f "$pattern" || true)"
  if [ -z "$pids" ]; then
    echo "==> $label: not running"
    return 0
  fi
  echo "==> Stopping $label ($pids)"
  kill $pids 2>/dev/null || true
  sleep 1
  pids="$(pgrep -f "$pattern" || true)"
  if [ -n "$pids" ]; then
    kill -9 $pids 2>/dev/null || true
  fi
}

kill_pattern "backend" "alphadesk.main"
kill_pattern "frontend (next dev)" "next dev -p ${FRONTEND_PORT}"
kill_pattern "frontend (next-server)" "next-server"

echo ""
echo "Backend and frontend stopped. Infra (timescaledb, redis) left running —"
echo "use 'docker compose down' in $REPO_DIR if you want those stopped too."
