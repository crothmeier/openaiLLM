#!/bin/bash
set -euo pipefail

# NVMe Storage Verification Script

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== NVMe Model Storage Verification ==="
echo ""

# Check NVMe mount
echo "1. Checking NVMe mount point..."
if mountpoint -q /mnt/nvme; then
    echo -e "${GREEN}✓${NC} /mnt/nvme is mounted"
    df -h /mnt/nvme | tail -1
else
    echo -e "${RED}✗${NC} /mnt/nvme is not mounted!"
    exit 1
fi
echo ""

# Check directory structure
echo "2. Checking directory structure..."
DIRS=("/mnt/nvme/hf-cache" "/mnt/nvme/models" "/mnt/nvme/ollama")
for dir in "${DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo -e "${GREEN}✓${NC} $dir exists"
        echo "  Size: $(du -sh $dir 2>/dev/null | cut -f1)"
    else
        echo -e "${RED}✗${NC} $dir does not exist"
    fi
done
echo ""

# Check environment variables
echo "3. Checking environment variables..."
ENV_VARS=("HF_HOME" "TRANSFORMERS_CACHE" "OLLAMA_MODELS")
for var in "${ENV_VARS[@]}"; do
    if [ -n "${!var:-}" ]; then
        echo -e "${GREEN}✓${NC} $var = ${!var}"
    else
        echo -e "${YELLOW}⚠${NC} $var is not set in current shell"
    fi
done
echo ""

# Check system-wide environment
echo "4. Checking /etc/environment..."
if [ -f /etc/environment ]; then
    if grep -q "HF_HOME" /etc/environment; then
        echo -e "${GREEN}✓${NC} HF_HOME configured in /etc/environment"
    else
        echo -e "${YELLOW}⚠${NC} HF_HOME not in /etc/environment"
    fi
    
    if grep -q "OLLAMA_MODELS" /etc/environment; then
        echo -e "${GREEN}✓${NC} OLLAMA_MODELS configured in /etc/environment"
    else
        echo -e "${YELLOW}⚠${NC} OLLAMA_MODELS not in /etc/environment"
    fi
fi
echo ""

# Check for stray cache files
echo "5. Checking for stray cache files..."
STRAY_LOCATIONS=(
    "$HOME/.cache/huggingface"
    "$HOME/.cache/torch"
    "$HOME/.ollama"
)

for loc in "${STRAY_LOCATIONS[@]}"; do
    if [ -L "$loc" ]; then
        target=$(readlink -f "$loc")
        if [[ "$target" == /mnt/nvme/* ]]; then
            echo -e "${GREEN}✓${NC} $loc → $target (symlink to NVMe)"
        else
            echo -e "${YELLOW}⚠${NC} $loc → $target (not on NVMe)"
        fi
    elif [ -d "$loc" ]; then
        size=$(du -sh "$loc" 2>/dev/null | cut -f1 || echo "0")
        if [ "$size" != "0" ]; then
            echo -e "${YELLOW}⚠${NC} $loc exists with data (size: $size)"
        else
            echo -e "${GREEN}✓${NC} $loc exists but empty"
        fi
    else
        echo -e "${GREEN}✓${NC} $loc does not exist"
    fi
done
echo ""

# Check Python environment
echo "6. Verifying Python/HF configuration..."
python3 - << 'PYTHON_CHECK' 2>/dev/null || echo -e "${YELLOW}⚠${NC} Python check failed (transformers may not be installed)"
import os
import sys
try:
    from transformers import file_utils
    cache_dir = file_utils.default_cache_path
    if "/mnt/nvme" in cache_dir:
        print(f"✓ Transformers cache: {cache_dir}")
    else:
        print(f"⚠ Transformers cache not on NVMe: {cache_dir}")
except ImportError:
    print("⚠ transformers library not installed")

try:
    from huggingface_hub import constants
    hf_cache = constants.HF_HUB_CACHE
    if "/mnt/nvme" in hf_cache:
        print(f"✓ HF Hub cache: {hf_cache}")
    else:
        print(f"⚠ HF Hub cache not on NVMe: {hf_cache}")
except ImportError:
    print("⚠ huggingface_hub library not installed")
PYTHON_CHECK
echo ""

# Check disk usage
echo "7. NVMe storage usage:"
echo "------------------------"
df -h /mnt/nvme
echo ""
echo "Top directories by size:"
du -sh /mnt/nvme/* 2>/dev/null | sort -rh | head -5
echo ""

# Check for model files
echo "8. Model files on NVMe:"
echo "------------------------"
echo "Searching for model files (*.safetensors, *.bin, *.gguf)..."
find /mnt/nvme -type f \( -name "*.safetensors" -o -name "*.bin" -o -name "*.gguf" \) 2>/dev/null | head -10 || echo "No model files found yet"
echo ""

# Summary
echo "=== Summary ==="
WARNINGS=$(grep -c "⚠" /tmp/verify_output 2>/dev/null || echo 0)
ERRORS=$(grep -c "✗" /tmp/verify_output 2>/dev/null || echo 0)

if [ "$ERRORS" -gt 0 ]; then
    echo -e "${RED}Some errors detected. Please run setup-nvme-models.sh first.${NC}"
elif [ "$WARNINGS" -gt 0 ]; then
    echo -e "${YELLOW}Setup mostly complete. Some warnings detected - may need to source ~/.bashrc or restart shell.${NC}"
else
    echo -e "${GREEN}All checks passed! NVMe storage is properly configured.${NC}"
fi