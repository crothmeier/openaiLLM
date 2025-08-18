#!/bin/bash
set -euo pipefail

echo "Testing determinism with temp=0 and seed pinning..."

# Test 1: Basic determinism check with normalized output
echo -n "Test 1: Basic determinism... "
H1=$(python3 - <<'PY'
from src.gptoss_client import GPTOSSClient
import re, hashlib
txt = GPTOSSClient().complete_deterministic("Return token: ALPHA", max_tokens=8)
norm = re.sub(r'\s+', ' ', txt.strip())
print(hashlib.md5(norm.encode()).hexdigest())
PY
)

H2=$(python3 - <<'PY'
from src.gptoss_client import GPTOSSClient
import re, hashlib
txt = GPTOSSClient().complete_deterministic("Return token: ALPHA", max_tokens=8)
norm = re.sub(r'\s+', ' ', txt.strip())
print(hashlib.md5(norm.encode()).hexdigest())
PY
)

if [ "$H1" = "$H2" ]; then
    echo "✅ PASS (hash: ${H1:0:8}...)"
else
    echo "❌ FAIL"
    echo "  Hash 1: $H1"
    echo "  Hash 2: $H2"
    exit 1
fi

# Test 2: Single request with identical prompts
echo -n "Test 2: Identical prompts... "
python3 - <<'PY'
from src.gptoss_client import GPTOSSClient
c = GPTOSSClient()
a = c.complete_deterministic("Echo exactly: ZETA.", max_tokens=4)
b = c.complete_deterministic("Echo exactly: ZETA.", max_tokens=4)
if a.strip() == b.strip():
    print("✅ PASS")
else:
    print(f"❌ FAIL\n  Output 1: {repr(a)}\n  Output 2: {repr(b)}")
    exit(1)
PY

# Test 3: Parallel determinism (still deterministic if seed fixed and greedy)
echo -n "Test 3: Parallel requests... "
python3 - <<'PY'
import concurrent.futures
from src.gptoss_client import GPTOSSClient

def one():
    return GPTOSSClient().complete_deterministic("Echo: RHO.", max_tokens=2)

with concurrent.futures.ThreadPoolExecutor(4) as ex:
    outs = list(ex.map(lambda _: one(), range(4)))

unique = set(o.strip() for o in outs)
if len(unique) == 1:
    print(f"✅ PASS (all 4 outputs identical)")
else:
    print(f"❌ FAIL\n  Got {len(unique)} unique outputs: {unique}")
    exit(1)
PY

# Test 4: OpenAI client determinism
echo -n "Test 4: OpenAI client... "
python3 - <<'PY'
from src.openai_client import complete_deterministic
import hashlib, re

txt1 = complete_deterministic("Return: BETA", max_tokens=4)
txt2 = complete_deterministic("Return: BETA", max_tokens=4)

norm1 = re.sub(r'\s+', ' ', txt1.strip())
norm2 = re.sub(r'\s+', ' ', txt2.strip())

if norm1 == norm2:
    h = hashlib.md5(norm1.encode()).hexdigest()
    print(f"✅ PASS (hash: {h[:8]}...)")
else:
    print(f"❌ FAIL\n  Output 1: {repr(txt1)}\n  Output 2: {repr(txt2)}")
    exit(1)
PY

echo ""
echo "All determinism tests passed! ✅"