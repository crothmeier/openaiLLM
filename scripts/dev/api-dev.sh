#!/usr/bin/env bash
set -euo pipefail

# API development server startup script
# Usage: ./scripts/dev/api-dev.sh [module] [symbol]

MOD="${1:-server.api}"
SYM="${2:-app}"
PORT="${PORT:-8001}"

echo "Starting FastAPI server..."
echo "Module: $MOD"
echo "Symbol: $SYM"
echo "Port: $PORT"

OPTS=(--host 0.0.0.0 --port "$PORT" --log-level info)
export PYTHONPATH=.

# Check if it's a factory function
if [[ "$SYM" == "create_app" ]]; then
  echo "Using factory pattern..."
  exec uvicorn "$MOD:$SYM" --factory "${OPTS[@]}"
else
  echo "Using app instance..."
  exec uvicorn "$MOD:$SYM" "${OPTS[@]}"
fi