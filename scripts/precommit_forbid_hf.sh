#!/usr/bin/env bash
set -euo pipefail
fail=0

# Block staged HF artifacts by extension/name
while IFS= read -r -d '' p; do
  case "$p" in
    *.safetensors|*.gguf|*.pt|*pytorch_model*.bin|*tokenizer.model|*spiece.model)
      echo "ERROR: HF/model artifact staged: $p" >&2
      fail=1
      ;;
  esac
done < <(git diff --cached --name-only -z)

# Block large files (>25MB) staged
while IFS= read -r -d '' f; do
  sha=$(git ls-files -s -- "$f" | awk '{print $2}')
  [ -z "${sha:-}" ] && continue
  size=$(git cat-file -s "$sha" 2>/dev/null || echo 0)
  if [ "$size" -gt $((25*1024*1024)) ]; then
    echo "ERROR: Large file (>25MB) staged: $f ($size bytes)" >&2
    fail=1
  fi
done < <(git diff --cached --name-only -z)

exit $fail
