#!/bin/bash
set -euo pipefail

# NVMe Model Storage Setup Script
# Ensures all AI models (HF, vLLM, Ollama) use /mnt/nvme

# Source security validation module
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./security/validate.sh
source "${SCRIPT_DIR}/security/validate.sh"

NVME_BASE="/mnt/nvme"
USER_NAME="${SUDO_USER:-$USER}"

# Validate base path
if ! validate_path "$NVME_BASE" "/" >/dev/null; then
    echo "Error: Invalid NVMe base path" >&2
    exit 1
fi

echo "=== Setting up NVMe storage for AI models ==="

# Step 1: Create directory structure
echo "Creating NVMe directory structure..."
sudo mkdir -p ${NVME_BASE}/{hf-cache,models,ollama}
sudo chown -R ${USER_NAME}:${USER_NAME} ${NVME_BASE}
echo "✓ Directories created and permissions set"

# Step 2: Configure Hugging Face environment
echo "Configuring Hugging Face environment..."

# Add to user's bashrc
if ! grep -q "HF_HOME=${NVME_BASE}/hf-cache" ~/.bashrc; then
    cat >> ~/.bashrc << 'EOF'

# Hugging Face NVMe cache configuration
export HF_HOME=/mnt/nvme/hf-cache
export TRANSFORMERS_CACHE=/mnt/nvme/hf-cache
export HUGGINGFACE_HUB_CACHE=/mnt/nvme/hf-cache
EOF
    echo "✓ Added HF environment variables to ~/.bashrc"
else
    echo "✓ HF environment variables already configured"
fi

# Add to system-wide environment
if ! grep -q "HF_HOME=${NVME_BASE}/hf-cache" /etc/environment; then
    echo "Adding system-wide environment variables..."
    echo "HF_HOME=${NVME_BASE}/hf-cache" | sudo tee -a /etc/environment
    echo "TRANSFORMERS_CACHE=${NVME_BASE}/hf-cache" | sudo tee -a /etc/environment
    echo "HUGGINGFACE_HUB_CACHE=${NVME_BASE}/hf-cache" | sudo tee -a /etc/environment
    echo "✓ Added HF environment variables to /etc/environment"
fi

# Step 3: Configure Ollama
echo "Configuring Ollama..."
if ! grep -q "OLLAMA_MODELS=${NVME_BASE}/ollama" ~/.bashrc; then
    echo "export OLLAMA_MODELS=${NVME_BASE}/ollama" >> ~/.bashrc
    echo "✓ Added OLLAMA_MODELS to ~/.bashrc"
fi

if ! grep -q "OLLAMA_MODELS=${NVME_BASE}/ollama" /etc/environment; then
    echo "OLLAMA_MODELS=${NVME_BASE}/ollama" | sudo tee -a /etc/environment
    echo "✓ Added OLLAMA_MODELS to /etc/environment"
fi

# Step 4: Create symlinks for compatibility
echo "Creating compatibility symlinks..."
mkdir -p ~/.cache
if [ ! -L ~/.cache/huggingface ]; then
    ln -s ${NVME_BASE}/hf-cache ~/.cache/huggingface
    echo "✓ Created HF cache symlink"
fi

if [ ! -L ~/.ollama ]; then
    ln -s ${NVME_BASE}/ollama ~/.ollama
    echo "✓ Created Ollama symlink"
fi

# Step 5: Export variables for current session
export HF_HOME=${NVME_BASE}/hf-cache
export TRANSFORMERS_CACHE=${NVME_BASE}/hf-cache
export HUGGINGFACE_HUB_CACHE=${NVME_BASE}/hf-cache
export OLLAMA_MODELS=${NVME_BASE}/ollama

echo ""
echo "=== Setup complete! ==="
echo "Storage paths configured:"
echo "  HF Cache: ${NVME_BASE}/hf-cache"
echo "  Models: ${NVME_BASE}/models"
echo "  Ollama: ${NVME_BASE}/ollama"
echo ""
echo "Note: Run 'source ~/.bashrc' or restart your shell for changes to take effect"