#!/bin/bash
# CI Determinism Gate - Exit code 13 on failure as requested
set -euo pipefail

echo "Running CI Determinism Gate..."

# Quick hash check using raw client for maximum compatibility
H1=$(python3 - <<'PY'
from src.gptoss_client import GPTOSSClient
import re, hashlib
txt = GPTOSSClient().complete_deterministic("Return token: ALPHA", max_tokens=8)
print(hashlib.md5(re.sub(r'\\s+',' ',txt.strip()).encode()).hexdigest())
PY
)

H2=$(python3 - <<'PY'
from src.gptoss_client import GPTOSSClient
import re, hashlib
txt = GPTOSSClient().complete_deterministic("Return token: ALPHA", max_tokens=8)
print(hashlib.md5(re.sub(r'\\s+',' ',txt.strip()).encode()).hexdigest())
PY
)

if [ "$H1" = "$H2" ]; then
    echo "✅ Determinism gate PASSED (hash: ${H1:0:8}...)"
    exit 0
else
    echo "❌ Non-deterministic at temp=0"
    echo "  Hash 1: $H1"
    echo "  Hash 2: $H2"
    exit 13
fi