#!/bin/bash
set -euo pipefail

# NVMe Model Storage Setup Script with Enhanced Reliability
# Ensures all AI models (HF, vLLM, Ollama) use /mnt/nvme

# Source utility functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/nvme_checks.sh"

# Source security validation module if it exists
if [[ -f "${SCRIPT_DIR}/../security/validate.sh" ]]; then
    source "${SCRIPT_DIR}/../security/validate.sh"
fi

NVME_BASE="/mnt/nvme"
USER_NAME="${SUDO_USER:-$USER}"

# Trap for error handling and rollback
ENV_BACKUP=""
trap 'handle_error' ERR

handle_error() {
    echo "Error occurred during setup!" >&2
    if [[ -n "$ENV_BACKUP" ]] && [[ -f "$ENV_BACKUP" ]]; then
        echo "Attempting to restore /etc/environment backup..." >&2
        sudo mv "$ENV_BACKUP" /etc/environment
        echo "Backup restored from $ENV_BACKUP" >&2
    fi
    release_lock 2>/dev/null || true
    exit 1
}

cleanup_on_exit() {
    release_lock 2>/dev/null || true
    # Clean up old backups (keep last 7 days)
    cleanup_old_backups "/etc/environment" 7 2>/dev/null || true
}

trap 'cleanup_on_exit' EXIT

echo "=== Setting up NVMe storage for AI models with reliability safeguards ==="

# Check if NVMe is mounted FIRST
echo "Checking NVMe mount status..."
check_nvme_mounted
echo "✓ NVMe is properly mounted at /mnt/nvme"

# Acquire lock to prevent concurrent runs
echo "Acquiring operation lock..."
acquire_lock
echo "✓ Lock acquired successfully"

# Validate base path if validation module exists
if command -v validate_path >/dev/null 2>&1; then
    if ! validate_path "$NVME_BASE" "/" >/dev/null; then
        die "Invalid NVMe base path"
    fi
fi

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
    echo "✓ HF environment variables already configured in ~/.bashrc"
fi

# Add to system-wide environment with backup
if ! grep -q "HF_HOME=${NVME_BASE}/hf-cache" /etc/environment; then
    echo "Backing up /etc/environment before modification..."
    ENV_BACKUP=$(backup_file /etc/environment)
    echo "✓ Backup created at $ENV_BACKUP"
    
    echo "Adding system-wide environment variables..."
    echo "HF_HOME=${NVME_BASE}/hf-cache" | sudo tee -a /etc/environment >/dev/null
    echo "TRANSFORMERS_CACHE=${NVME_BASE}/hf-cache" | sudo tee -a /etc/environment >/dev/null
    echo "HUGGINGFACE_HUB_CACHE=${NVME_BASE}/hf-cache" | sudo tee -a /etc/environment >/dev/null
    echo "✓ Added HF environment variables to /etc/environment"
else
    echo "✓ HF environment variables already in /etc/environment"
fi

# Step 3: Configure Ollama
echo "Configuring Ollama..."
if ! grep -q "OLLAMA_MODELS=${NVME_BASE}/ollama" ~/.bashrc; then
    echo "export OLLAMA_MODELS=${NVME_BASE}/ollama" >> ~/.bashrc
    echo "✓ Added OLLAMA_MODELS to ~/.bashrc"
else
    echo "✓ OLLAMA_MODELS already configured in ~/.bashrc"
fi

if ! grep -q "OLLAMA_MODELS=${NVME_BASE}/ollama" /etc/environment; then
    if [[ -z "$ENV_BACKUP" ]]; then
        echo "Backing up /etc/environment before modification..."
        ENV_BACKUP=$(backup_file /etc/environment)
        echo "✓ Backup created at $ENV_BACKUP"
    fi
    echo "OLLAMA_MODELS=${NVME_BASE}/ollama" | sudo tee -a /etc/environment >/dev/null
    echo "✓ Added OLLAMA_MODELS to /etc/environment"
else
    echo "✓ OLLAMA_MODELS already in /etc/environment"
fi

# Step 4: Create symlinks for compatibility
echo "Creating compatibility symlinks..."
mkdir -p ~/.cache
if [ ! -L ~/.cache/huggingface ]; then
    # Remove existing directory if it exists
    if [ -d ~/.cache/huggingface ] && [ ! -L ~/.cache/huggingface ]; then
        echo "  Removing existing ~/.cache/huggingface directory..."
        rm -rf ~/.cache/huggingface
    fi
    ln -s ${NVME_BASE}/hf-cache ~/.cache/huggingface
    echo "✓ Created HF cache symlink"
else
    echo "✓ HF cache symlink already exists"
fi

if [ ! -L ~/.ollama ]; then
    # Remove existing directory if it exists
    if [ -d ~/.ollama ] && [ ! -L ~/.ollama ]; then
        echo "  Removing existing ~/.ollama directory..."
        rm -rf ~/.ollama
    fi
    ln -s ${NVME_BASE}/ollama ~/.ollama
    echo "✓ Created Ollama symlink"
else
    echo "✓ Ollama symlink already exists"
fi

# Step 5: Export variables for current session
export HF_HOME=${NVME_BASE}/hf-cache
export TRANSFORMERS_CACHE=${NVME_BASE}/hf-cache
export HUGGINGFACE_HUB_CACHE=${NVME_BASE}/hf-cache
export OLLAMA_MODELS=${NVME_BASE}/ollama

# Clear the ENV_BACKUP variable since setup completed successfully
ENV_BACKUP=""

echo ""
echo "=== Setup complete! ==="
echo "Storage paths configured:"
echo "  HF Cache: ${NVME_BASE}/hf-cache"
echo "  Models: ${NVME_BASE}/models"
echo "  Ollama: ${NVME_BASE}/ollama"
echo ""
echo "Disk space available: $(df -h /mnt/nvme | awk 'NR==2 {print $4}')"
echo ""
echo "Note: Run 'source ~/.bashrc' or restart your shell for changes to take effect"