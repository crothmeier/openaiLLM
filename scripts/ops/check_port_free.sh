#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-}"
[ -n "$PORT" ] || { echo "usage: $0 <port>"; exit 2; }

# More reliable check using lsof
if command -v lsof >/dev/null 2>&1; then
    if sudo lsof -i ":${PORT}" -P -n | grep -q LISTEN; then
        echo "Port ${PORT} is already in use."
        exit 1
    fi
else
    # Fallback to ss
    if ss -ltn "( sport = :${PORT} )" | grep -q ":${PORT}"; then
        echo "Port ${PORT} is already in use."
        exit 1
    fi
fi

echo "Port ${PORT} is available."
