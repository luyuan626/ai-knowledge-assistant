#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$PROJECT_DIR/run/uvicorn.pid"
LOG_FILE="$PROJECT_DIR/run/uvicorn.log"

mkdir -p "$PROJECT_DIR/run"

# Keep provider credentials on the server only. .env is ignored by Git and is
# loaded just before Uvicorn starts so app.config can read the variables.
if [[ -f "$PROJECT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.env"
  set +a
fi

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Service is already running (PID $(cat "$PID_FILE"))."
  exit 0
fi

cd "$PROJECT_DIR/backend"
nohup "$PROJECT_DIR/.venv/bin/uvicorn" app.main:app --host 0.0.0.0 --port 8000 \
  > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
echo "Started on http://127.0.0.1:8000 (PID $(cat "$PID_FILE"))."
