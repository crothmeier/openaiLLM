#!/usr/bin/env bash
set -euo pipefail

echo "=== Homelab LLM Stack Status ==="
services=(llamacpp ollama)
for s in "${services[@]}"; do
  if systemctl is-active --quiet "$s"; then
    echo "✓ $s"
  else
    echo "✗ $s"
  fi
done

echo -e "\n=== Port Listeners (8001,8010,8080) ==="
ss -ltnpH 2>/dev/null | awk '$4 ~ /:(8001|8010|8080)$/ {print $4 "\t" $7}' \
  | sed -e 's/users://;s/"//g' -e 's/,fd=.*//' \
  || echo "No listeners found"

echo -e "\n=== Mountpoints & Space ==="
for mp in /mnt/models /mnt/nvme; do
  if mountpoint -q "$mp"; then
    src=$(findmnt -no SOURCE "$mp"); fstype=$(findmnt -no FSTYPE "$mp"); opts=$(findmnt -no OPTIONS "$mp")
    df -h "$mp" | awk 'NR==2{printf "%s: %s free of %s  (src=%s, fstype=%s, opts=%s)\n","'"$mp"'", $4, $2, "'"$src"'", "'"$fstype"'", "'"$opts"'"}'
  else
    echo "$mp: NOT-MOUNTED"
  fi
done

echo -e "\n=== Models Deployed (GGUF count) ==="
MODELS_ROOT=""
for d in /mnt/models /mnt/nvme/models; do
  if [ -d "$d" ]; then MODELS_ROOT="$d"; break; fi
done
: "${MODELS_ROOT:=/mnt/models}"
count=$(find "$MODELS_ROOT" -type f -name '*.gguf' 2>/dev/null | wc -l | tr -d ' ')
echo "$MODELS_ROOT -> $count files (*.gguf)"

echo -e "\n=== HTTP Health ==="
if ss -ltnH | awk '$4 ~ /:8010$/ {found=1} END{exit !found}'; then
  # llama.cpp
  curl -sS --max-time 3 -X POST http://127.0.0.1:8010/completion \
    -H 'content-type: application/json' \
    -d '{"prompt":"ping","n_predict":8}' \
    | jq -r '.model,.timings.total_ms' 2>/dev/null \
    || echo "llama.cpp: completion probe failed"
  curl -sS --max-time 2 http://127.0.0.1:8010/metrics | head -n 3 || echo "llama.cpp: metrics probe failed or disabled"
else
  echo "llama.cpp: no listener on 127.0.0.1:8010"
fi

if ss -ltnH | awk '$4 ~ /:8001$/ {found=1} END{exit !found}'; then
  curl -sS --max-time 3 http://127.0.0.1:8001/metrics | head -n 3 || echo "API: metrics probe failed"
else
  echo "API: no listener on 127.0.0.1:8001"
fi

echo -e "\n=== Recent Errors (journal) ==="
journalctl -p err -u llamacpp.service --since -5min --no-pager || true