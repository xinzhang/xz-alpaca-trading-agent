#!/usr/bin/env bash
# Starts infra (TimescaleDB, Redis), the backend, and the frontend dashboard
# for local dev — skips anything already running. Symlinked as `alpaca-agent-start`
# in ~/bin so it can be called from any directory. Stop with `alpaca-agent-stop`.
set -uo pipefail

REPO_DIR="/Users/xinzhang/projects/algoTrading/alpaca-trading-agent"
LOG_DIR="/tmp/alpaca-trading-agent"
mkdir -p "$LOG_DIR"

BACKEND_PORT="$(grep -E '^PORT=' "$REPO_DIR/.env" 2>/dev/null | cut -d= -f2)"
BACKEND_PORT="${BACKEND_PORT:-8682}"
FRONTEND_PORT="$(grep -oE -- '-p [0-9]+' "$REPO_DIR/frontend/package.json" 2>/dev/null | grep -oE '[0-9]+' | head -1)"
FRONTEND_PORT="${FRONTEND_PORT:-8681}"

echo "==> Infra (timescaledb, redis)"
(cd "$REPO_DIR" && docker compose up -d timescaledb redis)

if curl -sf "http://localhost:${BACKEND_PORT}/health" >/dev/null 2>&1; then
  echo "==> Backend already running on :${BACKEND_PORT}"
else
  echo "==> Starting backend on :${BACKEND_PORT}"
  (cd "$REPO_DIR" && nohup uv run python -m alphadesk.main >"$LOG_DIR/backend.log" 2>&1 & disown)
fi

if curl -sf "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1; then
  echo "==> Frontend already running on :${FRONTEND_PORT}"
else
  echo "==> Starting frontend on :${FRONTEND_PORT}"
  (cd "$REPO_DIR/frontend" && nohup npm run dev >"$LOG_DIR/frontend.log" 2>&1 & disown)
fi

echo "==> Waiting for both to come up..."
for _ in $(seq 1 30); do
  backend_ok=0; frontend_ok=0
  curl -sf "http://localhost:${BACKEND_PORT}/health" >/dev/null 2>&1 && backend_ok=1
  curl -sf "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1 && frontend_ok=1
  [ "$backend_ok" = "1" ] && [ "$frontend_ok" = "1" ] && break
  sleep 1
done

echo ""
echo "Backend:  http://localhost:${BACKEND_PORT}  (log: $LOG_DIR/backend.log)"
echo "Frontend: http://localhost:${FRONTEND_PORT}  (log: $LOG_DIR/frontend.log)"
