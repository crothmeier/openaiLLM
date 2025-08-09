#!/usr/bin/env bash
set -euo pipefail
PORT="${1:-}"; [ -n "$PORT" ] || { echo "usage: $0 <port>"; exit 2; }
if ss -ltn | awk '{print $4}' | grep -q ":${PORT}$"; then
  echo "Port ${PORT} is already in use."
  exit 1
fi
echo "Port ${PORT} is available."