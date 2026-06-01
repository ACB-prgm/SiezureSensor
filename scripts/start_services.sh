#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_DIR="$ROOT_DIR/server"
WEB_DIR="$ROOT_DIR/web/labeling_workbench"

SERVER_PYTHON="${SERVER_PYTHON:-$SERVER_DIR/.venv/bin/python}"
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"
WEB_HOST="${WEB_HOST:-0.0.0.0}"
WEB_PORT="${WEB_PORT:-5173}"
API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:$API_PORT}"

api_pid=""
web_pid=""

log() {
  printf '%s\n' "$*"
}

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  trap - INT TERM EXIT

  if [ -n "$web_pid" ] && kill -0 "$web_pid" 2>/dev/null; then
    log "Stopping workbench process $web_pid..."
    kill "$web_pid" 2>/dev/null || true
  fi

  if [ -n "$api_pid" ] && kill -0 "$api_pid" 2>/dev/null; then
    log "Stopping FastAPI process $api_pid..."
    kill "$api_pid" 2>/dev/null || true
  fi

  if [ -n "$web_pid" ]; then
    wait "$web_pid" 2>/dev/null || true
  fi
  if [ -n "$api_pid" ]; then
    wait "$api_pid" 2>/dev/null || true
  fi
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "$1 is required but was not found on PATH."
}

is_reachable() {
  curl -fsS "$1" >/dev/null 2>&1
}

wait_for_url() {
  url="$1"
  label="$2"
  attempts="${3:-40}"

  log "Waiting for $label at $url..."
  i=1
  while [ "$i" -le "$attempts" ]; do
    if is_reachable "$url"; then
      log "$label is ready."
      return 0
    fi
    sleep 0.5
    i=$((i + 1))
  done

  fail "$label did not become reachable at $url."
}

local_ip() {
  ipconfig getifaddr en0 2>/dev/null \
    || ipconfig getifaddr en1 2>/dev/null \
    || hostname -I 2>/dev/null | awk '{print $1}'
}

trap cleanup INT TERM EXIT

require_command curl
require_command npm

if [ ! -x "$SERVER_PYTHON" ]; then
  fail "Server virtualenv not found at $SERVER_PYTHON. Run: cd server && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt"
fi

if [ ! -d "$WEB_DIR/node_modules" ]; then
  fail "Workbench dependencies are missing. Run: cd web/labeling_workbench && npm install"
fi

if is_reachable "$API_BASE_URL/health"; then
  log "FastAPI is already reachable at $API_BASE_URL."
else
  log "Starting FastAPI on $API_HOST:$API_PORT..."
  (
    cd "$SERVER_DIR"
    "$SERVER_PYTHON" -m uvicorn app.main:app --host "$API_HOST" --port "$API_PORT"
  ) &
  api_pid="$!"
  wait_for_url "$API_BASE_URL/health" "FastAPI"
fi

WEB_LOCAL_URL="http://127.0.0.1:$WEB_PORT"
if is_reachable "$WEB_LOCAL_URL"; then
  log "Workbench is already reachable at $WEB_LOCAL_URL."
else
  log "Starting workbench on $WEB_HOST:$WEB_PORT..."
  (
    cd "$WEB_DIR"
    npm run dev -- --host "$WEB_HOST" --port "$WEB_PORT"
  ) &
  web_pid="$!"
  wait_for_url "$WEB_LOCAL_URL" "Workbench"
fi

LAN_IP="$(local_ip || true)"

log ""
log "Services are running."
log "Dashboard: $WEB_LOCAL_URL"
log "API:       $API_BASE_URL"
if [ -n "$LAN_IP" ]; then
  log "LAN dashboard: http://$LAN_IP:$WEB_PORT"
  log "LAN API:       http://$LAN_IP:$API_PORT"
fi
log ""
log "Press Ctrl+C to stop services started by this script."
log "Processes already running before this script started will be left alone."

while true; do
  if [ -n "$api_pid" ] && ! kill -0 "$api_pid" 2>/dev/null; then
    wait "$api_pid" || true
    fail "FastAPI process exited."
  fi

  if [ -n "$web_pid" ] && ! kill -0 "$web_pid" 2>/dev/null; then
    wait "$web_pid" || true
    fail "Workbench process exited."
  fi

  sleep 2
done
